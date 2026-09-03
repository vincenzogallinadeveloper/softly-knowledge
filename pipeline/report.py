"""A maintainer's-eye audit of the knowledge base.

    python3 -m pipeline.report

Unlike `build`, this never fails — it's a health dashboard, not a gate. It reads
the source files (so it sees drafts too) and surfaces the things a human curator
cares about: what still needs clinician review, where illustrations and second
sources are thin, which atoms are isolated in the graph, and which relation types
are going unused. Pair it with `build --check` (the hard gate) in a review.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .loader import Atom, load_corpus

REPO_ROOT = Path(__file__).resolve().parent.parent
ALL_RELATION_TYPES = {"is-a", "part-of", "related-to", "symptom-of",
                      "associated-with", "see-also"}
_BODY = ("glance", "overview", "deep", "when_to_see_doctor", "red_flags")


def _published(corpus):
    return [a for a in corpus.atoms if a.status == "published"]


def collect(corpus, today: date) -> dict:
    atoms = corpus.atoms
    pub = _published(corpus)
    pub_ids = {a.id for a in pub}

    # review
    reviewed = [a for a in pub if a.frontmatter.get("review", {}).get("reviewedBy")
                not in (None, "", "unreviewed")]
    overdue = []
    for a in pub:
        due = (a.frontmatter.get("review") or {}).get("nextReviewDue")
        if isinstance(due, str):
            try:
                if date.fromisoformat(due) < today:
                    overdue.append((a.id, due))
            except ValueError:
                pass

    # sources
    by_org, by_license, single_source, urls = {}, {}, [], set()
    for a in pub:
        srcs = a.frontmatter.get("sources") or []
        if len(srcs) == 1:
            single_source.append(a.id)
        for s in srcs:
            by_org[s["org"]] = by_org.get(s["org"], 0) + 1
            by_license[s["license"]] = by_license.get(s["license"], 0) + 1
            urls.add(s["url"])

    # relations
    rel_by_type = {}
    linked = set()
    for a in pub:
        for r in a.relations:
            rel_by_type[r["type"]] = rel_by_type.get(r["type"], 0) + 1
            if r.get("target") in pub_ids and r["target"] != a.id:
                linked.add(a.id)
                linked.add(r["target"])
    isolated = sorted(pub_ids - linked)

    # completeness
    def is_care(a: Atom):
        return a.frontmatter.get("type") in ("symptom", "condition")

    missing_deep = [a.id for a in pub if not a.renditions.get("deep")]
    care_no_redflags = [a.id for a in pub
                        if is_care(a) and not a.renditions.get("red_flags")]

    # illustrations
    illus_atoms = [a.id for a in pub if a.frontmatter.get("illustrationId")]
    cats_no_illus = [c.id for c in corpus.categories if not c.illustration_id]

    # per category
    cats = []
    for c in sorted(corpus.categories, key=lambda c: (c.order, c.id)):
        n_pub = sum(1 for a in pub if a.frontmatter.get("category") == c.id)
        n_draft = sum(1 for a in atoms if a.status == "draft"
                      and a.frontmatter.get("category") == c.id)
        cats.append((c.id, n_pub, n_draft, c.illustration_id is not None))

    return {
        "atoms_total": len(atoms),
        "published": len(pub),
        "draft": len(atoms) - len(pub),
        "categories": len(corpus.categories),
        "paths": len(corpus.paths),
        "paths_published": sum(1 for p in corpus.paths if p.status == "published"),
        "relations_total": sum(rel_by_type.values()),
        "rel_by_type": rel_by_type,
        "unused_relation_types": sorted(ALL_RELATION_TYPES - set(rel_by_type)),
        "reviewed": len(reviewed),
        "overdue": overdue,
        "by_org": by_org,
        "by_license": by_license,
        "single_source": single_source,
        "distinct_urls": len(urls),
        "isolated": isolated,
        "missing_deep": missing_deep,
        "care_no_redflags": care_no_redflags,
        "illus_atoms": len(illus_atoms),
        "cats_no_illus": cats_no_illus,
        "per_category": cats,
    }


def render(d: dict) -> str:
    L = []
    def line(s=""): L.append(s)

    line("Softly Knowledge — content report")
    line("=" * 40)
    line(f"Atoms:      {d['published']} published, {d['draft']} draft "
         f"({d['atoms_total']} total)")
    line(f"Categories: {d['categories']}   Paths: {d['paths_published']} published "
         f"({d['paths']} total)")
    line(f"Relations:  {d['relations_total']}  "
         + "  ".join(f"{k}={v}" for k, v in sorted(d['rel_by_type'].items())))
    if d["unused_relation_types"]:
        line(f"  ⚠ unused relation types: {', '.join(d['unused_relation_types'])}")

    line()
    line("Per category (published / draft, ★=has hero illustration)")
    for cid, npub, ndraft, hero in d["per_category"]:
        flag = "★" if hero else " "
        warn = "  ← empty" if npub == 0 else ""
        line(f"  {flag} {cid:<26} {npub:>2} / {ndraft}{warn}")

    line()
    line("Clinician review")
    line(f"  reviewed: {d['reviewed']} / {d['published']} "
         + ("✓" if d['reviewed'] == d['published'] else "← none reviewed yet"
            if d['reviewed'] == 0 else ""))
    if d["overdue"]:
        line(f"  ⚠ {len(d['overdue'])} overdue: "
             + ", ".join(f"{i} ({due})" for i, due in d["overdue"]))

    line()
    line("Sources")
    line("  by org:     " + "  ".join(f"{k}={v}" for k, v in sorted(d['by_org'].items())))
    line("  by licence: " + "  ".join(f"{k}={v}" for k, v in sorted(d['by_license'].items())))
    line(f"  distinct URLs: {d['distinct_urls']}")
    if d["single_source"]:
        line(f"  single-source atoms ({len(d['single_source'])}): "
             + ", ".join(d["single_source"]))

    line()
    line("Completeness")
    line(f"  atoms without Deep ({len(d['missing_deep'])}): "
         + (", ".join(d["missing_deep"]) or "none"))
    line(f"  symptom/condition atoms without Red flags ({len(d['care_no_redflags'])}): "
         + (", ".join(d["care_no_redflags"]) or "none"))

    line()
    line("Illustrations")
    line(f"  atoms with a topic image: {d['illus_atoms']} / {d['published']}")
    line(f"  categories still without a hero image ({len(d['cats_no_illus'])}): "
         + (", ".join(d["cats_no_illus"]) or "none"))

    if d.get("isolated"):
        line()
        line(f"Graph: isolated atoms ({len(d['isolated'])}): " + ", ".join(d["isolated"]))

    return "\n".join(L)


def _parse_args(argv):
    p = argparse.ArgumentParser(prog="pipeline.report",
                                description="Audit the knowledge base (never fails).")
    p.add_argument("--content", type=Path, default=REPO_ROOT / "content" / "en")
    p.add_argument("--categories", type=Path,
                   default=REPO_ROOT / "categories" / "categories.yaml")
    p.add_argument("--paths", type=Path, default=REPO_ROOT / "paths" / "paths.yaml")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    corpus = load_corpus(args.content, args.categories, args.paths)
    data = collect(corpus, date.today())
    print(render(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
