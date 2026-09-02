# Softly Knowledge

The open, cited, source-of-truth knowledge base behind [Softly](https://…) — a free,
private, ad-free women's-health app.

Softly Knowledge is **not a blog, a website, or a set of articles.** It is a small
**knowledge graph**: every medical concept exists exactly **once** (one atom), is
**linked** to related concepts, and carries **at least one citation to a tier-1 public-health
source.** The Softly app compiles this graph into an offline, on-device store and uses it to
build its *Discover* section and to give *Softly Intelligence* its explanations. Nothing here
is fetched at runtime; the app ships the knowledge inside it.

> [!IMPORTANT]
> **This is educational content, not medical advice.** Softly does not diagnose, treat, or
> replace a healthcare professional. Every atom summarises material published by recognised
> health authorities and links back to it. Always consult a qualified professional for medical
> decisions. See [`docs/EDITORIAL_POLICY.md`](docs/EDITORIAL_POLICY.md).

## How it works

```
  Markdown atoms (this repo, human-authored, git-reviewed)
        │   one file = one concept, YAML frontmatter + prose
        ▼
  Validation + build pipeline            ← enforces the invariants
        │   every link resolves · every atom has a source · no duplicate ids · schema-valid
        ▼
  knowledge.sqlite  (FTS5, read-only)    ← bundled in the Softly app
        │
        ├─▶  Discover  (dynamic educational section)
        └─▶  Softly Intelligence  (contextual explanations)
```

- **Authoring format:** Markdown + YAML frontmatter — diff-able, reviewable by a clinician
  without opening Xcode, versioned in git.
- **Runtime format:** a compiled read-only **SQLite** database (full-text search + graph
  traversal), bundled in the app. Works fully offline; no server, no tracking.
- **Localization:** the **graph is language-neutral** (ids, relations, sources). Only the
  **display text** is localized, as overlays per language. Adding a concept = one node + N
  translations, never "rewrite the graph 50 times."

## Repository layout

```
softly-knowledge/
├── README.md
├── LICENSE                 MIT — the pipeline / tooling
├── CONTENT_LICENSE.md      CC BY-SA 4.0 — the knowledge content
├── CONTRIBUTING.md
├── docs/
│   ├── EDITORIAL_POLICY.md   allowed sources, tone, safety, review cadence
│   ├── ATOM_SCHEMA.md        the shape of one atom (frontmatter + body + relations)
│   └── DISCOVER_DESIGN.md    the app section this feeds (IA + interactions)
├── schema/
│   └── atom.schema.json      machine-checkable frontmatter schema
├── categories/
│   └── categories.yaml       the fixed top-level taxonomy
└── content/
    └── en/                   source-language atoms (one file per concept)
        └── hormones/
            └── estrogen.md   ← worked reference example
```

## Licensing

- **Tooling / pipeline:** MIT (`LICENSE`).
- **Knowledge content** (`content/**`, `categories/**`): **CC BY-SA 4.0**
  (`CONTENT_LICENSE.md`). You may reuse it with attribution and share-alike. Citations to the
  original authorities are preserved in each atom.

## Status

Foundations. The build pipeline, translations, and the bulk of the content come next — but the
**invariants are fixed first**, so quality is enforced by tooling, not by discipline.
