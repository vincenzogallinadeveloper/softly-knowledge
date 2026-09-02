"""Load and parse the repository's source-of-truth files.

- categories/categories.yaml  -> the fixed taxonomy
- content/<lang>/**/*.md       -> one atom per file (frontmatter + renditions)

Parsing only. All correctness checks live in ``rules.py``; here we fail only on
files we cannot structurally read at all (missing/malformed frontmatter).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

SOURCE_LANG = "en"

# Body H2 headings (docs/ATOM_SCHEMA.md §2) -> canonical rendition keys.
RENDITION_HEADINGS = {
    "glance": "glance",
    "overview": "overview",
    "deep": "deep",
    "when to see a doctor": "when_to_see_doctor",
    "red flags": "red_flags",
}

_H2 = re.compile(r"^##\s+(.+?)\s*$")


class LoadError(Exception):
    """A file could not be parsed at all (structural, not a validation issue)."""


@dataclass
class Atom:
    id: str
    slug: str                     # filename stem (must equal id; checked in rules)
    lang: str
    path: Path
    frontmatter: dict
    renditions: Dict[str, str]    # canonical key -> section text
    unknown_headings: List[str]   # H2s that are not known renditions
    checksum: str                 # sha256 of the raw file bytes

    @property
    def status(self) -> str:
        return self.frontmatter.get("status", "")

    @property
    def relations(self) -> List[dict]:
        return self.frontmatter.get("relations", []) or []


@dataclass
class Category:
    id: str
    order: int
    color_token: str
    illustration_id: Optional[str]
    title: str
    summary: Optional[str]


@dataclass
class LearningPath:
    id: str
    order: int
    illustration_id: Optional[str]
    status: str
    title: str
    summary: Optional[str]
    steps: List[str]
    data: dict                    # the raw YAML entry, for schema validation


@dataclass
class Corpus:
    atoms: List[Atom]
    categories: List[Category]
    categories_checksum: str = ""
    category_ids: set = field(default_factory=set)
    paths: List["LearningPath"] = field(default_factory=list)
    paths_checksum: str = ""


def _normalize_yaml_dates(node):
    """PyYAML turns ISO dates into date/datetime objects; the schema expects
    strings. Convert them back so validation sees the on-disk representation."""
    if isinstance(node, dict):
        return {k: _normalize_yaml_dates(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_normalize_yaml_dates(v) for v in node]
    if isinstance(node, (_dt.date, _dt.datetime)):
        return node.isoformat()
    return node


def _split_frontmatter(text: str, path: Path):
    """Return (frontmatter_text, body_text). Raises LoadError if absent."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise LoadError(f"{path}: file must start with a '---' frontmatter block")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    raise LoadError(f"{path}: frontmatter '---' block is never closed")


def _parse_renditions(body: str):
    """Split the Markdown body into H2 sections.

    Returns (renditions, unknown_headings). Content before the first H2 is
    ignored (it should be empty)."""
    renditions: Dict[str, str] = {}
    unknown: List[str] = []
    current_key: Optional[str] = None
    current_heading: Optional[str] = None
    buf: List[str] = []

    def flush():
        text = "\n".join(buf).strip()
        if current_key is not None:
            renditions[current_key] = text
        elif current_heading is not None:
            unknown.append(current_heading)

    for line in body.splitlines():
        m = _H2.match(line)
        if m:
            flush()
            heading = m.group(1).strip()
            buf = []
            current_heading = heading
            current_key = RENDITION_HEADINGS.get(heading.lower())
        else:
            buf.append(line)
    flush()
    return renditions, unknown


def load_atom(path: Path, lang: str = SOURCE_LANG) -> Atom:
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    fm_text, body = _split_frontmatter(text, path)
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        raise LoadError(f"{path}: invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise LoadError(f"{path}: frontmatter must be a YAML mapping")
    fm = _normalize_yaml_dates(fm)
    renditions, unknown = _parse_renditions(body)
    return Atom(
        id=str(fm.get("id", "")),
        slug=path.stem,
        lang=lang,
        path=path,
        frontmatter=fm,
        renditions=renditions,
        unknown_headings=unknown,
        checksum=checksum,
    )


def load_categories(path: Path):
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    doc = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(doc, dict) or "categories" not in doc:
        raise LoadError(f"{path}: expected a top-level 'categories:' list")
    cats: List[Category] = []
    for entry in doc["categories"]:
        cats.append(
            Category(
                id=str(entry["id"]),
                order=int(entry.get("order", 0)),
                color_token=str(entry.get("colorToken", "")),
                illustration_id=entry.get("illustrationId"),
                title=str(entry.get("title", "")),
                summary=entry.get("summary"),
            )
        )
    return cats, checksum


def load_paths(path: Path):
    """Load learning paths from paths/paths.yaml. Returns (paths, checksum).
    A missing file is not an error — it just means no paths yet."""
    if not path.exists():
        return [], ""
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    doc = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(doc, dict) or "paths" not in doc:
        raise LoadError(f"{path}: expected a top-level 'paths:' list")
    paths: List[LearningPath] = []
    for entry in doc["paths"] or []:
        paths.append(
            LearningPath(
                id=str(entry.get("id", "")),
                order=int(entry.get("order", 0)),
                illustration_id=entry.get("illustrationId"),
                status=str(entry.get("status", "")),
                title=str(entry.get("title", "")),
                summary=entry.get("summary"),
                steps=list(entry.get("steps") or []),
                data=entry,
            )
        )
    return paths, checksum


def load_corpus(content_dir: Path, categories_file: Path,
                paths_file: Optional[Path] = None,
                lang: str = SOURCE_LANG) -> Corpus:
    categories, cat_checksum = load_categories(categories_file)
    atoms = [load_atom(p, lang) for p in sorted(content_dir.rglob("*.md"))]
    paths, paths_checksum = ([], "")
    if paths_file is not None:
        paths, paths_checksum = load_paths(paths_file)
    return Corpus(
        atoms=atoms,
        categories=categories,
        categories_checksum=cat_checksum,
        category_ids={c.id for c in categories},
        paths=paths,
        paths_checksum=paths_checksum,
    )
