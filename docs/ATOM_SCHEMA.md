# Atom schema

An **atom** is one medical concept — a hormone, a phase, a symptom, a condition, a test — that
exists **exactly once** in the whole knowledge base. One file, one concept, one stable id.

An atom is a Markdown file: **YAML frontmatter** (structured, language-neutral metadata + the
source-language strings) followed by a **body** of prose split into named sections ("renditions").

The machine-checkable version lives in [`../schema/atom.schema.json`](../schema/atom.schema.json).
This document is the human explanation. When the two disagree, the JSON Schema wins.

---

## 1. Frontmatter

```yaml
id: estrogen                 # REQUIRED. Stable, unique, kebab-case, PERMANENT. Never rename.
type: hormone                # REQUIRED. See "types" below.
category: hormones           # REQUIRED. Home category id (categories/categories.yaml).
title: Estrogen              # REQUIRED. Source-language display title (localizable).
aliases: [oestrogen]         # optional. Search synonyms in the source language (localizable).
phases: [follicular]         # optional. Cycle phases this atom relates to (drives phase recs).
illustrationId: estrogen     # optional. Topic image id. Falls back to category art / placeholder.
status: draft                # REQUIRED. draft | published. Only `published` atoms ship.

relations:                   # optional list. Typed, closed set (see below). Target = another id.
  - { type: related-to, target: progesterone }
  - { type: part-of,    target: menstrual-cycle }

sources:                     # REQUIRED. At least ONE tier-1 citation.
  - org: NHS                 # REQUIRED. One of the allowed orgs (EDITORIAL_POLICY.md).
    title: "Periods and fertility in the menstrual cycle"   # REQUIRED.
    url: https://www.nhs.uk/…                               # REQUIRED. Direct link.
    published: 2023-01-01    # optional. Source's own date if shown.
    accessed: 2026-09-02     # REQUIRED. When a human last verified the link + claim.
    license: OGL-3.0         # REQUIRED. Source's reuse licence (see EDITORIAL_POLICY.md).

review:                      # REQUIRED.
  reviewedBy: unreviewed     # A clinician's name/handle, or the literal "unreviewed".
  reviewedOn: null           # date | null
  nextReviewDue: 2027-09-02  # REQUIRED. Medical info goes stale; a decade-long system tracks it.
  contentVersion: 1          # Bump on every material content change.
```

### Types (`type`)
A closed set describing the **nature** of the atom (not the same as its category):

`concept` · `hormone` · `phase` · `symptom` · `condition` · `contraception` · `test` · `life-stage`

`category` says *where it lives* in the UI; `type` says *what it is* and lets the app render it
correctly (a `condition` card shows "when to see a doctor"; a `hormone` card does not).

### Relations (closed set)
Only these six edge types are allowed. Keep the graph typed and predictable — no open ontology.

| type             | direction / meaning                              | example                                   |
|------------------|--------------------------------------------------|-------------------------------------------|
| `is-a`           | A is a kind of B                                 | `estradiol` → `is-a` → `estrogen`         |
| `part-of`        | A is a component/stage of B                      | `ovulation` → `part-of` → `menstrual-cycle` |
| `related-to`     | general, symmetric association                   | `estrogen` → `related-to` → `progesterone` |
| `symptom-of`     | A is a sign of B                                 | `spotting` → `symptom-of` → `pcos`        |
| `associated-with`| A commonly co-occurs with / is linked to B       | `pcos` → `associated-with` → `insulin-resistance` |
| `see-also`       | editorial "read next" pointer                    | `contraception` → `see-also` → `fertility` |

Rules: a `target` **must** be the `id` of another atom (the build fails on a dangling link).
Do **not** invent edge types. If you feel you need one, open an issue — extending the set is a
deliberate, reviewed decision, because every edge type is something the UI must know how to draw.

### Forbidden in relations
No `treated-with` / `cure` / `dosage` edges. Softly is educational, never prescriptive. Management
options, when relevant, are described in prose under **When to see a doctor**, framed as
"things a clinician may discuss," never as instructions.

---

## 2. Body — renditions

The body is Markdown split into **named H2 sections**. The pipeline reads them by heading. A
concept is written **once** but has several *renditions* for different contexts, so nothing is
duplicated across the app.

```markdown
## Glance
One sentence, ≤ 160 characters. Plain language. Used for tooltips and Softly Intelligence
inline explanations. No jargon without the plain word beside it.

## Overview
The card-level explanation shown in Discover. 2–4 short paragraphs. Calm, warm, concrete.
This is the default body of a topic card.

## Deep            (optional)
A longer explanation for the full topic page. Still education, still sourced.

## When to see a doctor   (recommended for `symptom` and `condition`; optional otherwise)
Plain guidance on when it's worth talking to a professional. Never diagnostic.

## Red flags       (optional; for symptoms/conditions with urgent signs)
- Bulleted, unambiguous "seek urgent care if…" signals. These MUST always surface — Softly
  Intelligence never buries a red flag behind a softer message.
```

- **Every user-facing string is localizable.** The English body is the *source*; translations
  are overlays (see the app's existing 50-language pipeline). Ids, relations, and sources are
  **never** translated.
- Keep prose **original** — summarise the source in your own words. Never paste source text.
  See `EDITORIAL_POLICY.md` for why (licensing + accuracy).

---

## 3. Worked example

See [`../content/en/hormones/estrogen.md`](../content/en/hormones/estrogen.md) for a complete,
schema-valid reference atom. Copy it as the starting point for a new concept.

## 4. What the build enforces

The pipeline (added next) fails the build if any of these is violated — so the invariants hold
without relying on anyone remembering them:

- `id` is unique and matches the filename slug.
- Frontmatter validates against `atom.schema.json`.
- Every `relations[].target` resolves to an existing atom.
- Every atom has ≥ 1 source with a required `org`, `title`, `url`, `accessed`, `license`.
- `category` exists in `categories.yaml`; `type` is in the allowed set.
- A `published` atom has a non-empty `## Glance` and `## Overview`.
- No orphan atoms (every published atom is reachable from at least one category or relation).
