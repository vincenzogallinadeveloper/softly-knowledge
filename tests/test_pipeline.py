"""Tests for the Softly Knowledge build pipeline.

Stdlib only (unittest + tempfile) — no third-party test runner, so CI needs
nothing beyond PyYAML. Run with:

    python3 -m unittest discover -s tests

The suite locks in the invariants the whole project relies on: the schema
validator, frontmatter/rendition parsing, a valid corpus compiling to a working
SQLite + FTS store, and each fatal rule actually failing the build (plus the
draft-dangling-link warning that must NOT fail it).
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import textwrap
import unittest
from datetime import date
from pathlib import Path

from pipeline import loader, report, rules
from pipeline.compile_sqlite import compile_db
from pipeline.schema_validator import validate

REPO_ROOT = Path(__file__).resolve().parent.parent
ATOM_SCHEMA = json.loads((REPO_ROOT / "schema" / "atom.schema.json").read_text("utf-8"))
PATH_SCHEMA = json.loads((REPO_ROOT / "schema" / "path.schema.json").read_text("utf-8"))
FAR_FUTURE = date(2099, 1, 1)  # keeps fixtures from ever tripping the overdue-review warning

CATEGORIES_YAML = textwrap.dedent(
    """
    categories:
      - id: hormones
        title: Hormones
        order: 1
        colorToken: brand
        illustrationId: cat-hormones
        summary: The messengers behind the cycle.
      - id: cycle-and-phases
        title: The cycle & its phases
        order: 2
        colorToken: brand
        summary: The phases of the cycle.
    """
).lstrip()


def atom_md(
    *,
    id="estrogen",
    type="hormone",
    category="hormones",
    title="Estrogen",
    status="published",
    relations=None,
    glance="A key hormone of the cycle.",
    overview="A calm, sourced overview paragraph.",
    extra_body="",
    next_review="2099-01-01",
):
    lines = [
        "---",
        f"id: {id}",
        f"type: {type}",
        f"category: {category}",
        f"title: {title}",
        f"status: {status}",
    ]
    if relations:
        lines.append("relations:")
        lines += [f"  - {{ type: {t}, target: {tgt} }}" for t, tgt in relations]
    lines += [
        "sources:",
        "  - org: NHS",
        '    title: "A source"',
        "    url: https://www.nhs.uk/x",
        "    accessed: 2026-09-03",
        "    license: OGL-3.0",
        "review:",
        "  reviewedBy: unreviewed",
        "  reviewedOn: null",
        f"  nextReviewDue: {next_review}",
        "  contentVersion: 1",
        "---",
    ]
    body = ""
    if glance is not None:
        body += f"\n## Glance\n{glance}\n"
    if overview is not None:
        body += f"\n## Overview\n{overview}\n"
    body += extra_body
    return "\n".join(lines) + "\n" + body


class Fixture:
    """A throwaway repo: content dir + categories + optional paths."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.content = tmp / "content" / "en"
        self.content.mkdir(parents=True)
        self.categories = tmp / "categories.yaml"
        self.categories.write_text(CATEGORIES_YAML, "utf-8")
        self.paths_file = tmp / "paths.yaml"

    def write_atom(self, filename, text):
        p = self.content / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")

    def write_paths(self, yaml_text):
        self.paths_file.write_text(yaml_text, "utf-8")

    def corpus(self):
        paths = self.paths_file if self.paths_file.exists() else None
        return loader.load_corpus(self.content, self.categories, paths)

    def report(self):
        return rules.check(self.corpus(), ATOM_SCHEMA, PATH_SCHEMA, today=date(2026, 9, 3))


class SchemaValidatorTests(unittest.TestCase):
    def test_valid_frontmatter(self):
        fm = loader.yaml.safe_load(
            atom_md().split("---", 2)[1]
        )
        fm = loader._normalize_yaml_dates(fm)
        self.assertEqual(validate(fm, ATOM_SCHEMA), [])

    def test_bad_type_enum(self):
        errs = validate({"id": "x", "type": "nope", "category": "hormones",
                         "title": "X", "status": "draft",
                         "sources": [{"org": "NHS", "title": "t",
                                      "url": "https://a", "accessed": "2026-09-03",
                                      "license": "OGL-3.0"}],
                         "review": {"reviewedBy": "unreviewed",
                                    "nextReviewDue": "2027-01-01",
                                    "contentVersion": 1}},
                        ATOM_SCHEMA)
        self.assertTrue(any("type" in e for e in errs))

    def test_additional_property_rejected(self):
        errs = validate({"id": "x", "surprise": 1}, ATOM_SCHEMA)
        self.assertTrue(any("surprise" in e for e in errs))

    def test_bad_date_format(self):
        errs = validate("2026-13-40", {"type": "string", "format": "date"})
        self.assertTrue(errs)

    def test_kebab_pattern(self):
        errs = validate("Not_Kebab", ATOM_SCHEMA["properties"]["id"])
        self.assertTrue(errs)

    def test_unknown_keyword_raises(self):
        with self.assertRaises(NotImplementedError):
            validate({}, {"type": "object", "patternProperties": {}})


class ParsingTests(unittest.TestCase):
    def test_renditions_split(self):
        text = atom_md(
            extra_body="\n## When to see a doctor\nSee a GP if…\n\n## Red flags\n- Urgent thing\n"
        )
        fm, body = loader._split_frontmatter(text, Path("x.md"))
        rends, unknown = loader._parse_renditions(body)
        self.assertEqual(rends["glance"], "A key hormone of the cycle.")
        self.assertIn("when_to_see_doctor", rends)
        self.assertIn("red_flags", rends)
        self.assertEqual(unknown, [])

    def test_unknown_heading_flagged(self):
        _, body = loader._split_frontmatter(
            atom_md(extra_body="\n## Mystery\nhi\n"), Path("x.md")
        )
        _, unknown = loader._parse_renditions(body)
        self.assertEqual(unknown, ["Mystery"])

    def test_missing_frontmatter_raises(self):
        with self.assertRaises(loader.LoadError):
            loader._split_frontmatter("no frontmatter here", Path("x.md"))

    def test_yaml_dates_normalized_to_strings(self):
        fm = loader._normalize_yaml_dates({"accessed": date(2026, 9, 3)})
        self.assertEqual(fm["accessed"], "2026-09-03")


class ValidCorpusTests(unittest.TestCase):
    def _valid_fixture(self, tmp):
        fx = Fixture(Path(tmp))
        fx.write_atom("hormones/estrogen.md", atom_md(
            id="estrogen", relations=[("related-to", "progesterone")]))
        fx.write_atom("hormones/progesterone.md", atom_md(
            id="progesterone", title="Progesterone",
            relations=[("related-to", "estrogen")]))
        return fx

    def test_passes_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self._valid_fixture(tmp).report()
            self.assertEqual(report.errors, [], report.errors)
            self.assertTrue(report.ok)

    def test_compiles_and_is_queryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self._valid_fixture(tmp)
            out = Path(tmp) / "knowledge.sqlite"
            stats = compile_db(fx.corpus(), out)
            self.assertEqual(stats["published"], 2)
            db = sqlite3.connect(out)
            self.assertEqual(db.execute("SELECT count(*) FROM atoms").fetchone()[0], 2)
            # FTS finds a word from the body
            hit = db.execute(
                "SELECT atom_id FROM atom_fts WHERE atom_fts MATCH 'overview'"
            ).fetchall()
            self.assertTrue(hit)
            # foreign keys + integrity hold
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            db.close()

    def test_draft_excluded_from_compile(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(
                id="estrogen", relations=[("related-to", "progesterone")]))
            fx.write_atom("hormones/progesterone.md", atom_md(
                id="progesterone", relations=[("related-to", "estrogen")]))
            fx.write_atom("hormones/draft-one.md", atom_md(
                id="draft-one", title="Draft", status="draft"))
            out = Path(tmp) / "k.sqlite"
            stats = compile_db(fx.corpus(), out)
            self.assertEqual(stats["published"], 2)  # draft not shipped


class InvariantTests(unittest.TestCase):
    def _errors(self, fx):
        return fx.report().errors

    def test_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(id="estrogen"))
            fx.write_atom("hormones/dup.md", atom_md(id="estrogen"))
            self.assertTrue(any("duplicate id" in e for e in self._errors(fx)))

    def test_id_slug_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/wrong-name.md", atom_md(id="estrogen"))
            self.assertTrue(any("filename slug" in e for e in self._errors(fx)))

    def test_published_dangling_relation_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(
                id="estrogen", relations=[("related-to", "ghost")]))
            self.assertTrue(any("does not resolve" in e for e in self._errors(fx)))

    def test_draft_dangling_relation_is_warning_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(
                id="estrogen", status="draft", relations=[("related-to", "ghost")]))
            report = fx.report()
            self.assertEqual([e for e in report.errors if "resolve" in e], [])
            self.assertTrue(any("does not resolve" in w for w in report.warnings))

    def test_published_missing_overview_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(id="estrogen", overview=None))
            self.assertTrue(any("Overview" in e for e in self._errors(fx)))

    def test_unknown_category_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(
                id="estrogen", category="not-real"))
            self.assertTrue(any("not defined in categories" in e
                                for e in self._errors(fx)))

    def test_published_relation_to_draft_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(
                id="estrogen", relations=[("related-to", "progesterone")]))
            fx.write_atom("hormones/progesterone.md", atom_md(
                id="progesterone", status="draft"))
            self.assertTrue(any("non-published target" in e for e in self._errors(fx)))


class PathTests(unittest.TestCase):
    def _fixture_with_atoms(self, tmp):
        fx = Fixture(Path(tmp))
        fx.write_atom("hormones/estrogen.md", atom_md(
            id="estrogen", relations=[("related-to", "progesterone")]))
        fx.write_atom("hormones/progesterone.md", atom_md(
            id="progesterone", relations=[("related-to", "estrogen")]))
        return fx

    def test_valid_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self._fixture_with_atoms(tmp)
            fx.write_paths(textwrap.dedent("""
                paths:
                  - id: p1
                    title: A path
                    order: 1
                    status: published
                    steps: [estrogen, progesterone]
            """))
            report = fx.report()
            self.assertEqual(report.errors, [], report.errors)
            out = Path(tmp) / "k.sqlite"
            stats = compile_db(fx.corpus(), out)
            self.assertEqual(stats["paths"], 1)

    def test_published_path_dangling_step_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self._fixture_with_atoms(tmp)
            fx.write_paths(textwrap.dedent("""
                paths:
                  - id: p1
                    title: A path
                    order: 1
                    status: published
                    steps: [estrogen, ghost]
            """))
            self.assertTrue(any("does not resolve" in e for e in fx.report().errors))

    def test_too_few_steps_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self._fixture_with_atoms(tmp)
            fx.write_paths(textwrap.dedent("""
                paths:
                  - id: p1
                    title: A path
                    order: 1
                    status: published
                    steps: [estrogen]
            """))
            self.assertTrue(any("minItems" in e for e in fx.report().errors))

    def test_duplicate_path_id_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self._fixture_with_atoms(tmp)
            fx.write_paths(textwrap.dedent("""
                paths:
                  - id: p1
                    title: A
                    order: 1
                    status: published
                    steps: [estrogen, progesterone]
                  - id: p1
                    title: B
                    order: 2
                    status: published
                    steps: [progesterone, estrogen]
            """))
            self.assertTrue(any("duplicate path id" in e for e in fx.report().errors))


class OverlayTests(unittest.TestCase):
    """Target-language overlays: translated strings win, English fills the gaps."""

    def _fixture(self, tmp):
        fx = Fixture(Path(tmp))
        fx.write_atom("hormones/estrogen.md", atom_md(
            id="estrogen", relations=[("related-to", "progesterone")]))
        fx.write_atom("hormones/progesterone.md", atom_md(
            id="progesterone", title="Progesterone",
            relations=[("related-to", "estrogen")]))
        return fx

    def test_overlay_translates_and_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self._fixture(tmp)
            catalog = {
                "_meta": {"lang": "it"},
                "atoms": {"estrogen": {"title": "Estrogeno",
                                       "glance": "Un ormone chiave."}},
                "categories": {"hormones": {"title": "Ormoni"}},
                "paths": {},
            }
            out = Path(tmp) / "k.sqlite"
            stats = compile_db(fx.corpus(), out, target_catalogs={"it": catalog})
            db = sqlite3.connect(out)
            db.row_factory = sqlite3.Row
            # translated atom shows Italian
            est = db.execute(
                "SELECT title, glance FROM atom_text WHERE atom_id='estrogen' "
                "AND lang='it'").fetchone()
            self.assertEqual(est["title"], "Estrogeno")
            # untranslated atom falls back to English
            prog = db.execute(
                "SELECT title FROM atom_text WHERE atom_id='progesterone' "
                "AND lang='it'").fetchone()
            self.assertEqual(prog["title"], "Progesterone")
            # category translated; both languages present
            cat = db.execute("SELECT title FROM category_text WHERE "
                             "category_id='hormones' AND lang='it'").fetchone()
            self.assertEqual(cat["title"], "Ormoni")
            langs = {r[0] for r in db.execute("SELECT code FROM languages")}
            self.assertEqual(langs, {"en", "it"})
            # Italian FTS finds the translated glance
            hit = db.execute("SELECT atom_id FROM atom_fts WHERE atom_fts MATCH "
                             "'ormone' AND lang='it'").fetchall()
            self.assertTrue(hit)
            db.close()
            # coverage is reported and partial
            done, total = stats["coverage"]["it"]
            self.assertGreater(total, done)  # not everything translated
            self.assertGreater(done, 0)      # but something is

    def test_no_catalogs_means_english_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = self._fixture(tmp)
            out = Path(tmp) / "k.sqlite"
            stats = compile_db(fx.corpus(), out)
            self.assertEqual(stats["coverage"], {})
            db = sqlite3.connect(out)
            langs = {r[0] for r in db.execute("SELECT code FROM languages")}
            self.assertEqual(langs, {"en"})
            db.close()


class ReportTests(unittest.TestCase):
    def test_collect_and_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            fx.write_atom("hormones/estrogen.md", atom_md(
                id="estrogen", relations=[("related-to", "progesterone")]))
            fx.write_atom("hormones/progesterone.md", atom_md(
                id="progesterone", title="Progesterone",
                relations=[("related-to", "estrogen")]))
            fx.write_atom("hormones/draft-x.md", atom_md(
                id="draft-x", title="Draft", status="draft"))
            data = report.collect(fx.corpus(), date(2026, 9, 3))
            self.assertEqual(data["published"], 2)
            self.assertEqual(data["draft"], 1)
            self.assertEqual(data["reviewed"], 0)  # fixtures are all unreviewed
            # only related-to is used here, so the other five are flagged unused
            self.assertIn("is-a", data["unused_relation_types"])
            self.assertIn("symptom-of", data["unused_relation_types"])
            # render produces a non-empty string without raising
            self.assertIn("content report", report.render(data))


if __name__ == "__main__":
    unittest.main()
