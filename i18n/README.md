# Localization (`i18n/`)

Softly Knowledge is a **language-neutral graph** with **localized text overlays**. Adding a
language never touches the graph — it only supplies translated strings.

## What is translated vs. never translated

| Translated (per language) | Never translated (shared by all languages) |
|---|---|
| atom `title`, `aliases` | atom `id`, `type`, `category`, `status` |
| renditions: `Glance`, `Overview`, `Deep`, `When to see a doctor`, `Red flags` | `relations`, `sources`, `phases`, `illustrationId`, `review` |
| category `title`, `summary` | category `id`, `order`, `colorToken`, `illustrationId` |
| learning-path `title`, `summary` | path `id`, `order`, `steps`, `illustrationId`, `status` |

The source language is **English** (`content/en/**`). The English strings live in the Markdown
atoms themselves — they are not duplicated here.

## Layout

```
i18n/
├── README.md
├── en/
│   └── catalog.en.json     ← GENERATED source catalog (the strings to translate)
└── <lang>/
    └── catalog.<lang>.json ← one per target language, same shape, translated values
```

## Workflow (reuses Softly's DeepL pipeline)

1. **Extract** the source strings from the atoms:
   ```bash
   python3 -m pipeline.i18n_extract        # writes i18n/en/catalog.en.json
   ```
   `catalog.en.json` is generated — never hand-edit it. Edit the Markdown atoms and re-extract.

2. **Translate** `catalog.en.json` into each target language with Softly's existing DeepL
   pipeline, writing `i18n/<lang>/catalog.<lang>.json` with identical keys and structure. Each
   catalog carries `_meta.source_content_checksum`, so the DeepL step can tell when the English
   source changed and only re-translate what moved.

3. **Compile.** The build overlays every catalog it finds under `i18n/<lang>/` into the database's
   `atom_text`, `category_text`, and `path_text` tables (one row per atom/category/path **per
   language**), plus a per-language FTS row so search works in that language. Any string not yet
   translated **falls back to English**, so a partial catalog still yields a complete, usable
   database. Just run the normal build:

   ```bash
   python3 -m pipeline.build          # picks up i18n/it/catalog.it.json automatically
   ```

   It prints a coverage line per language (e.g. `it: 62% translated (…); rest fall back to en`).
   The app then queries `WHERE lang = 'it'`; the English fallback rows mean nothing is ever blank.
   Getting a language into Discover is therefore just: drop the DeepL-produced
   `i18n/<lang>/catalog.<lang>.json` into place and rebuild.

## Rules

- **Keys are the language-neutral ids** (atom id, category id) plus the field name. They are
  stable and permanent, so a translation always maps back to exactly one node.
- **Structure, not prose, is the contract.** Every target catalog must keep every key present in
  the source (a `null` field stays `null`), so the overlay step never has to guess.
- **Don't localize the graph.** If a translation seems to need a different relation or source,
  that's a content change to the English atom, not a translation — make it upstream.
