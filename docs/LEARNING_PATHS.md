# Learning paths

A **learning path** is a curated, ordered reading sequence over existing atoms — the "Understand
your cycle in 5 steps" rail in Discover (see [`DISCOVER_DESIGN.md`](DISCOVER_DESIGN.md) §8). It is
**editorial ordering, not content**: a path never introduces a new concept and never duplicates
prose. Each step is simply the `id` of an atom, and the step's display (title, `Glance`,
illustration) comes from that atom.

Paths live in [`../paths/paths.yaml`](../paths/paths.yaml), mirroring how categories work. The
machine-checkable shape is [`../schema/path.schema.json`](../schema/path.schema.json).

## Shape

```yaml
paths:
  - id: understand-your-cycle          # stable, unique, kebab-case, permanent
    title: Understand your cycle in 5 steps   # localizable
    order: 1                           # display order in Discover
    illustrationId: path-understand-cycle     # optional; falls back to a placeholder
    status: published                  # draft | published — only published ships
    summary: A calm walk through the whole cycle and each of its four phases.  # localizable
    steps:                             # ordered atom ids, >= 2, no duplicates
      - menstrual-cycle
      - menstrual-phase
      - follicular-phase
      - ovulation
      - luteal-phase
```

**Language-neutral** (never translated): `id`, `order`, `steps`, `illustrationId`, `status`.
**Localizable** (overlaid per language, like atoms): `title`, `summary`.

## What the build enforces

- `id` is unique across paths and kebab-case; `title` is non-empty; `order` ≥ 1 (schema).
- `steps` has at least 2 entries and no duplicate atom (schema).
- Every step resolves to an existing atom; for a **published** path, every step must be a
  **published** atom (fatal). A **draft** path may reference an atom that doesn't exist yet
  (warning) — the same rule atoms' relations follow.
- Only **published** paths are compiled into `knowledge.sqlite`.

## In the database

Three tables, keyed by the same language-neutral ids:

- `paths(id, ord, illustration_id, status)`
- `path_text(path_id, lang, title, summary)` — the localized overlay
- `path_steps(path_id, position, atom_id)` — the ordered steps (`position` is 0-based); indexed by
  `atom_id` so the app can also ask "which paths include this atom?"

## Why a separate object (not a relation)

Paths are **ordered** and **curated for a reading experience**; the graph's `relations` are
**unordered, typed associations** for "Related" / "Keep exploring." Keeping them separate means an
atom's place in the graph never depends on which paths happen to feature it, and a path can be
re-sequenced or retired without touching a single atom.
