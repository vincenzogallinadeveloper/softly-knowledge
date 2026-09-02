# Build pipeline

Validates every atom against `schema/atom.schema.json` + the editorial invariants, then compiles
the **published** subset into an offline, read-only SQLite store with FTS5. Runs fully offline;
one small dependency (PyYAML).

## Install

```bash
pip install -r pipeline/requirements.txt
```

## Run

```bash
python3 -m pipeline.build            # validate, then compile build/knowledge.sqlite
python3 -m pipeline.build --check    # validate only (use this as the CI gate)
python3 -m pipeline.build --strict   # treat warnings as errors
python3 -m pipeline.i18n_extract     # write i18n/en/catalog.en.json (translatable strings)
```

Exit code is non-zero when validation fails, so `--check` doubles as the CI gate.

## What it enforces

Fatal (build fails):

- Frontmatter validates against `schema/atom.schema.json` (the schema is the source of truth).
- `id` is unique and equals the filename slug.
- `category` exists in `categories.yaml`; `type` is in the allowed set (via schema).
- Every atom has ≥ 1 source with `org`, `title`, `url`, `accessed`, `license` (via schema).
- A **published** atom has a non-empty `## Glance` and `## Overview`.
- A **published** atom's `relations[].target` resolves to another **published** atom.

Warnings (surfaced; promoted to fatal with `--strict`):

- A **draft** atom's relation points at a missing atom (fine while bootstrapping).
- An atom is isolated in the graph (no relations), or a published atom's review is overdue.
- `Glance` longer than 160 chars; an unrecognised `## Heading` in the body.

## What it produces

`build/knowledge.sqlite` — language-neutral graph tables (`atoms`, `relations`, `sources`,
`categories`, `atom_phases`), localized text tables (`atom_text`, `category_text`, keyed by
`lang`), an FTS5 index (`atom_fts`) over title + aliases + body, and a `meta` table carrying
`content_checksum`, `built_at`, counts, and schema/pipeline versions. Only `published` atoms ship.
The file is built to a temp path and atomically moved into place.

## Modules

| File | Role |
|---|---|
| `build.py` | CLI: orchestrates load → validate → compile |
| `loader.py` | parse `categories.yaml` + atom Markdown (frontmatter + renditions) |
| `schema_validator.py` | tiny, dependency-free JSON-Schema validator (the schema stays authoritative) |
| `rules.py` | the editorial + graph invariants |
| `compile_sqlite.py` | DDL + inserts + FTS + checksum |
| `i18n_extract.py` | extract translatable strings into `i18n/<lang>/catalog.<lang>.json` |
