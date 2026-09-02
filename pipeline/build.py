"""Softly Knowledge build CLI.

    python3 -m pipeline.build            # validate, then compile build/knowledge.sqlite
    python3 -m pipeline.build --check    # validate only (CI gate)
    python3 -m pipeline.build --strict   # treat warnings as errors

Exit code is non-zero when validation fails (or on any warning under --strict),
so the same command guards CI and produces the artifact locally.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .compile_sqlite import compile_db
from .loader import LoadError, load_corpus
from .rules import check

REPO_ROOT = Path(__file__).resolve().parent.parent


def _parse_args(argv):
    p = argparse.ArgumentParser(prog="pipeline.build",
                                description="Validate and compile Softly Knowledge.")
    p.add_argument("--content", type=Path, default=REPO_ROOT / "content" / "en",
                   help="source-language content directory (default: content/en)")
    p.add_argument("--categories", type=Path,
                   default=REPO_ROOT / "categories" / "categories.yaml")
    p.add_argument("--schema", type=Path,
                   default=REPO_ROOT / "schema" / "atom.schema.json")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "build" / "knowledge.sqlite")
    p.add_argument("--check", action="store_true",
                   help="validate only; do not compile the database")
    p.add_argument("--strict", action="store_true",
                   help="treat warnings as errors")
    p.add_argument("--quiet", action="store_true",
                   help="print only errors and the final status line")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    def say(*a):
        if not args.quiet:
            print(*a)

    say(f"Softly Knowledge pipeline v{__version__}")

    try:
        schema = json.loads(args.schema.read_text("utf-8"))
        corpus = load_corpus(args.content, args.categories)
    except (LoadError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"✗ load failed: {e}", file=sys.stderr)
        return 2

    published = sum(1 for a in corpus.atoms if a.status == "published")
    drafts = len(corpus.atoms) - published
    say(f"  loaded {len(corpus.atoms)} atom(s): {published} published, {drafts} draft"
        f"; {len(corpus.categories)} categories")

    report = check(corpus, schema)

    for w in report.warnings:
        say(f"  ⚠ {w}")
    for e in report.errors:
        print(f"  ✗ {e}", file=sys.stderr)

    fatal = bool(report.errors) or (args.strict and bool(report.warnings))
    if fatal:
        n = len(report.errors) + (len(report.warnings) if args.strict else 0)
        print(f"✗ validation failed ({n} problem(s), "
              f"{len(report.warnings)} warning(s))", file=sys.stderr)
        return 1

    say(f"✓ validation passed ({len(report.warnings)} warning(s))")

    if args.check:
        say("  --check: skipping compile")
        return 0

    if published == 0:
        say("  no published atoms yet — nothing to compile "
            "(run without --check once atoms are published)")
        return 0

    stats = compile_db(corpus, args.out)
    say(f"✓ compiled {stats['published']} atom(s), {stats['relations']} relation(s) "
        f"→ {stats['out']}")
    say(f"  content_checksum {stats['content_checksum'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
