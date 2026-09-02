"""Compile the validated, published atoms into build/knowledge.sqlite.

Language-neutral graph (atoms, relations, sources, categories) is separated from
localized text (*_text tables keyed by lang), so translations become overlays,
never a second graph. Only ``published`` atoms ship. Full-text search is a
standalone FTS5 index over title + aliases + body.

The database is built to a temporary file and atomically moved into place, so a
failed build never leaves a half-written artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .loader import Atom, Corpus, SOURCE_LANG

DB_SCHEMA_VERSION = 1
PIPELINE_VERSION = 1

_DDL = """
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE languages (
  code      TEXT PRIMARY KEY,
  name      TEXT NOT NULL,
  is_source INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE categories (
  id              TEXT PRIMARY KEY,
  ord             INTEGER NOT NULL,
  color_token     TEXT NOT NULL,
  illustration_id TEXT
);

CREATE TABLE category_text (
  category_id TEXT NOT NULL REFERENCES categories(id),
  lang        TEXT NOT NULL REFERENCES languages(code),
  title       TEXT NOT NULL,
  summary     TEXT,
  PRIMARY KEY (category_id, lang)
);

CREATE TABLE atoms (
  id              TEXT PRIMARY KEY,
  type            TEXT NOT NULL,
  category        TEXT NOT NULL REFERENCES categories(id),
  illustration_id TEXT,
  status          TEXT NOT NULL,
  content_version INTEGER NOT NULL,
  reviewed_by     TEXT NOT NULL,
  reviewed_on     TEXT,
  next_review_due TEXT NOT NULL,
  checksum        TEXT NOT NULL
);

CREATE TABLE atom_text (
  atom_id            TEXT NOT NULL REFERENCES atoms(id),
  lang               TEXT NOT NULL REFERENCES languages(code),
  title              TEXT NOT NULL,
  aliases            TEXT,
  glance             TEXT,
  overview           TEXT,
  deep               TEXT,
  when_to_see_doctor TEXT,
  red_flags          TEXT,
  PRIMARY KEY (atom_id, lang)
);

CREATE TABLE atom_phases (
  atom_id TEXT NOT NULL REFERENCES atoms(id),
  phase   TEXT NOT NULL,
  PRIMARY KEY (atom_id, phase)
);

CREATE TABLE relations (
  source_id TEXT NOT NULL REFERENCES atoms(id),
  type      TEXT NOT NULL,
  target_id TEXT NOT NULL REFERENCES atoms(id),
  PRIMARY KEY (source_id, type, target_id)
);
CREATE INDEX idx_relations_target ON relations(target_id);

CREATE TABLE sources (
  id        INTEGER PRIMARY KEY,
  atom_id   TEXT NOT NULL REFERENCES atoms(id),
  ord       INTEGER NOT NULL,
  org       TEXT NOT NULL,
  title     TEXT NOT NULL,
  url       TEXT NOT NULL,
  published TEXT,
  accessed  TEXT NOT NULL,
  license   TEXT NOT NULL
);
CREATE INDEX idx_sources_atom ON sources(atom_id);

CREATE VIRTUAL TABLE atom_fts USING fts5 (
  title,
  aliases,
  body,
  atom_id UNINDEXED,
  lang    UNINDEXED,
  tokenize = "unicode61 remove_diacritics 2"
);
"""

_BODY_FIELDS = ("glance", "overview", "deep", "when_to_see_doctor", "red_flags")


def _content_checksum(published: List[Atom], categories_checksum: str) -> str:
    h = hashlib.sha256()
    for atom in sorted(published, key=lambda a: a.id):
        h.update(atom.id.encode("utf-8"))
        h.update(b"\0")
        h.update(atom.checksum.encode("utf-8"))
        h.update(b"\n")
    h.update(b"categories\0")
    h.update(categories_checksum.encode("utf-8"))
    return h.hexdigest()


def compile_db(corpus: Corpus, out_path: Path, lang: str = SOURCE_LANG) -> dict:
    """Build the SQLite artifact. Returns a small stats dict for reporting."""
    published = [a for a in corpus.atoms if a.status == "published"]
    published.sort(key=lambda a: a.id)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(tmp_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_DDL)

        conn.execute(
            "INSERT INTO languages(code, name, is_source) VALUES (?, ?, 1)",
            (lang, "English"),
        )

        # Categories (sorted by display order for deterministic output).
        for cat in sorted(corpus.categories, key=lambda c: (c.order, c.id)):
            conn.execute(
                "INSERT INTO categories(id, ord, color_token, illustration_id) "
                "VALUES (?, ?, ?, ?)",
                (cat.id, cat.order, cat.color_token, cat.illustration_id),
            )
            conn.execute(
                "INSERT INTO category_text(category_id, lang, title, summary) "
                "VALUES (?, ?, ?, ?)",
                (cat.id, lang, cat.title, cat.summary),
            )

        # Atoms + localized text + phases + sources.
        for atom in published:
            fm = atom.frontmatter
            review = fm.get("review") or {}
            conn.execute(
                "INSERT INTO atoms(id, type, category, illustration_id, status, "
                "content_version, reviewed_by, reviewed_on, next_review_due, "
                "checksum) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    atom.id, fm["type"], fm["category"], fm.get("illustrationId"),
                    atom.status, review.get("contentVersion", 1),
                    review.get("reviewedBy", "unreviewed"), review.get("reviewedOn"),
                    review.get("nextReviewDue"), atom.checksum,
                ),
            )
            aliases = fm.get("aliases") or []
            r = atom.renditions
            conn.execute(
                "INSERT INTO atom_text(atom_id, lang, title, aliases, glance, "
                "overview, deep, when_to_see_doctor, red_flags) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    atom.id, lang, fm["title"], json.dumps(aliases, ensure_ascii=False),
                    r.get("glance"), r.get("overview"), r.get("deep"),
                    r.get("when_to_see_doctor"), r.get("red_flags"),
                ),
            )
            for phase in fm.get("phases") or []:
                conn.execute(
                    "INSERT INTO atom_phases(atom_id, phase) VALUES (?, ?)",
                    (atom.id, phase),
                )
            for ord_, src in enumerate(fm.get("sources") or []):
                conn.execute(
                    "INSERT INTO sources(atom_id, ord, org, title, url, published, "
                    "accessed, license) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        atom.id, ord_, src["org"], src["title"], src["url"],
                        src.get("published"), src["accessed"], src["license"],
                    ),
                )

        # Relations — only edges where both endpoints ship (validated for
        # published atoms, but we guard again so a stray draft edge can't leak).
        published_ids = {a.id for a in published}
        rel_rows = set()
        for atom in published:
            for rel in atom.relations:
                tgt = rel.get("target")
                if tgt in published_ids and tgt != atom.id:
                    rel_rows.add((atom.id, rel["type"], tgt))
        for source_id, rtype, target_id in sorted(rel_rows):
            conn.execute(
                "INSERT INTO relations(source_id, type, target_id) VALUES (?, ?, ?)",
                (source_id, rtype, target_id),
            )

        # Full-text index.
        for atom in published:
            r = atom.renditions
            body = "\n\n".join(r[f] for f in _BODY_FIELDS if r.get(f))
            aliases = " ".join(atom.frontmatter.get("aliases") or [])
            conn.execute(
                "INSERT INTO atom_fts(title, aliases, body, atom_id, lang) "
                "VALUES (?, ?, ?, ?, ?)",
                (atom.frontmatter["title"], aliases, body, atom.id, lang),
            )

        # Build metadata + semantic content version.
        checksum = _content_checksum(published, corpus.categories_checksum)
        meta = {
            "db_schema_version": str(DB_SCHEMA_VERSION),
            "pipeline_version": str(PIPELINE_VERSION),
            "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "default_lang": lang,
            "atom_count": str(len(published)),
            "category_count": str(len(corpus.categories)),
            "content_checksum": checksum,
        }
        for key, value in meta.items():
            conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)", (key, value))

        conn.execute("INSERT INTO atom_fts(atom_fts) VALUES ('optimize')")
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()

    os.replace(tmp_path, out_path)
    return {
        "published": len(published),
        "categories": len(corpus.categories),
        "relations": len(rel_rows),
        "content_checksum": checksum,
        "out": str(out_path),
    }
