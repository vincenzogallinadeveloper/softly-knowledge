# Contributing to Softly Knowledge

Thank you for helping make trustworthy, plain-language women's-health education freely available.
**Clinicians especially welcome** — reviewing an atom, adding a citation, or correcting nuance is
one of the most valuable things you can do here.

## Before anything, read
- [`docs/EDITORIAL_POLICY.md`](docs/EDITORIAL_POLICY.md) — sources, tone, safety, what's forbidden.
- [`docs/ATOM_SCHEMA.md`](docs/ATOM_SCHEMA.md) — the shape of one atom.

## Adding or editing an atom
1. Copy [`content/en/hormones/estrogen.md`](content/en/hormones/estrogen.md) as a template.
2. Put it under `content/en/<category-ish>/<id>.md`. The **`id` in the frontmatter must equal the
   filename slug** and is permanent — never rename an id once published.
3. Fill the frontmatter. **At least one tier-1 source is required**, with a real `url` you have
   opened and an `accessed` date. Only orgs in the policy are allowed.
4. Write the body in your **own words** — `## Glance` and `## Overview` are required to publish.
   Never paste source text.
5. Add `relations` to existing atoms where it helps the graph. Every `target` must be a real `id`.
6. Leave `status: draft` until it's ready and (ideally) reviewed. Only `published` atoms ship.

## Golden rules
- **One concept, one atom.** Don't create a second "Estrogen." Link, don't duplicate.
- **Educational, never diagnostic or prescriptive.** No "you have X," no dosages, no instructions.
- **Original prose + citation.** Summarise; never copy.
- **Surface red flags.** Urgent signs go in `## Red flags` and must never be softened.
- The graph is **language-neutral**; only display text is localized (translations come later, via
  Softly's existing pipeline). Never translate `id`, `relations`, or `sources`.

## Review
Pull requests are reviewed against the editorial policy and the schema (the build fails on a
dangling link, a missing source, a duplicate id, or a schema violation). A clinician review that
sets `review.reviewedBy` is gold — please note your credentials in the PR if you have them.

## Licensing of your contribution
By contributing you agree your content is released under **CC BY-SA 4.0** (see
[`CONTENT_LICENSE.md`](CONTENT_LICENSE.md)) and any tooling under **MIT** (see `LICENSE`).
