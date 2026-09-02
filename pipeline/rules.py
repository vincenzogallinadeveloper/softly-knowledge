"""The invariants the build enforces (docs/ATOM_SCHEMA.md §4 + EDITORIAL_POLICY).

Each check appends to ``errors`` (fatal — build fails) or ``warnings`` (surfaced
but non-fatal; promotable to errors with --strict). The functions here decide
*policy*; loading/parsing lives in ``loader.py`` and schema-shape in
``schema_validator.py``.

Relation resolution rule (agreed): a ``published`` atom's relations MUST resolve
to another ``published`` atom (fatal); a ``draft`` may point anywhere (warning).
Only ``published`` atoms are compiled into the database.
"""

from __future__ import annotations

from datetime import date
from typing import List, Tuple

from .loader import Atom, Corpus
from .schema_validator import validate


class Report:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def check(corpus: Corpus, schema: dict, path_schema: dict | None = None,
          today: date | None = None) -> Report:
    report = Report()
    today = today or date.today()
    atoms = corpus.atoms
    by_id = {}
    status_by_id = {}

    # --- id uniqueness + id/filename agreement -----------------------------
    for atom in atoms:
        if not atom.id:
            report.error(f"{atom.path}: frontmatter is missing 'id'")
            continue
        if atom.id in by_id:
            report.error(
                f"duplicate id '{atom.id}': {atom.path} and {by_id[atom.id].path}"
            )
        else:
            by_id[atom.id] = atom
        status_by_id[atom.id] = atom.status
        if atom.id != atom.slug:
            report.error(
                f"{atom.path}: id '{atom.id}' must equal the filename slug "
                f"'{atom.slug}'"
            )

    # --- per-atom checks ---------------------------------------------------
    for atom in atoms:
        _check_schema(atom, schema, report)
        _check_category(atom, corpus, report)
        _check_renditions(atom, report)
        _check_relations(atom, status_by_id, report)
        _check_review(atom, today, report)

    # --- graph reachability (orphans) --------------------------------------
    _check_orphans(atoms, report)

    # --- learning paths ----------------------------------------------------
    _check_paths(corpus, path_schema, status_by_id, report)

    return report


def _check_schema(atom: Atom, schema: dict, report: Report) -> None:
    for err in validate(atom.frontmatter, schema, path=f"{atom.path}::frontmatter"):
        report.error(err)


def _check_category(atom: Atom, corpus: Corpus, report: Report) -> None:
    cat = atom.frontmatter.get("category")
    if cat and cat not in corpus.category_ids:
        report.error(
            f"{atom.path}: category '{cat}' is not defined in categories.yaml"
        )


def _check_renditions(atom: Atom, report: Report) -> None:
    for heading in atom.unknown_headings:
        report.warn(f"{atom.path}: unrecognised body section '## {heading}'")
    if atom.status == "published":
        if not atom.renditions.get("glance"):
            report.error(f"{atom.path}: published atom needs a non-empty '## Glance'")
        if not atom.renditions.get("overview"):
            report.error(f"{atom.path}: published atom needs a non-empty '## Overview'")
        glance = atom.renditions.get("glance", "")
        if len(glance) > 160:
            report.warn(
                f"{atom.path}: Glance is {len(glance)} chars (guideline ≤ 160)"
            )


def _check_relations(atom: Atom, status_by_id: dict, report: Report) -> None:
    published = atom.status == "published"
    for rel in atom.relations:
        target = rel.get("target")
        if target == atom.id:
            report.warn(f"{atom.path}: relation targets itself ('{target}')")
            continue
        if target not in status_by_id:
            msg = (f"{atom.path}: relation target '{target}' "
                   f"({rel.get('type')}) does not resolve to any atom")
            report.error(msg) if published else report.warn(msg)
        elif published and status_by_id[target] != "published":
            report.error(
                f"{atom.path}: published atom links to non-published target "
                f"'{target}' — publish the target or drop the relation"
            )


def _check_review(atom: Atom, today: date, report: Report) -> None:
    review = atom.frontmatter.get("review") or {}
    due = review.get("nextReviewDue")
    if isinstance(due, str):
        try:
            if date.fromisoformat(due) < today and atom.status == "published":
                report.warn(f"{atom.path}: review overdue (nextReviewDue {due})")
        except ValueError:
            pass  # schema validation already flags a malformed date


def _check_paths(corpus: Corpus, path_schema, status_by_id: dict,
                 report: Report) -> None:
    seen: dict = {}
    for path in corpus.paths:
        where = f"paths.yaml::{path.id or '<no id>'}"
        if path_schema is not None:
            for err in validate(path.data, path_schema, path=where):
                report.error(err)
        if not path.id:
            continue
        if path.id in seen:
            report.error(f"duplicate path id '{path.id}' in paths.yaml")
        seen[path.id] = path

        published = path.status == "published"
        for pos, step in enumerate(path.steps):
            if step not in status_by_id:
                msg = f"{where}: step {pos} '{step}' does not resolve to any atom"
                report.error(msg) if published else report.warn(msg)
            elif published and status_by_id[step] != "published":
                report.error(
                    f"{where}: published path includes non-published atom "
                    f"'{step}' — publish it or drop the step"
                )


def _check_orphans(atoms: List[Atom], report: Report) -> None:
    """Every published atom must be reachable — from its category (always true,
    since `category` is required and validated) or via a graph relation. An atom
    with no relations at all is reachable by category browse but isolated in the
    graph, which starves 'Related' / 'Keep exploring', so we warn."""
    published = {a.id for a in atoms if a.status == "published"}
    linked: set = set()
    for atom in atoms:
        if atom.status != "published":
            continue
        for rel in atom.relations:
            tgt = rel.get("target")
            if tgt in published and tgt != atom.id:
                linked.add(atom.id)
                linked.add(tgt)
    for atom_id in sorted(published - linked):
        report.warn(
            f"atom '{atom_id}': isolated in the graph (no relations to/from "
            f"another published atom)"
        )
