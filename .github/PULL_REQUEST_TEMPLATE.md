<!--
Thanks for contributing to Softly Knowledge! Please read
docs/EDITORIAL_POLICY.md and docs/ATOM_SCHEMA.md first, then tick the boxes that
apply. Delete sections that don't fit (e.g. a pipeline-only change).
-->

## What this changes
<!-- One or two sentences. Which atoms/paths/tooling, and why. -->

## Content checklist (for atom / path changes)
- [ ] **One concept, one atom** — no duplicate of an existing concept; I linked instead.
- [ ] Every source is a **tier-1 org from the editorial policy**, and I **opened each link** and
      confirmed it supports the text.
- [ ] Each source has a real `url`, an `accessed` date, and a `license`.
- [ ] Prose is **my own words** — no source text pasted (any quote ≤15 words, attributed).
- [ ] Published atoms have a non-empty **`## Glance` and `## Overview`**.
- [ ] `symptom` / `condition` atoms have **When to see a doctor**, and any urgent signs are in
      **`## Red flags`** (never softened).
- [ ] Nothing **diagnostic or prescriptive** — no "you have X", no dosages, no instructions.
- [ ] `id` equals the filename slug and (if editing) is unchanged.

## Local checks
- [ ] `python3 -m pipeline.build --check` passes.
- [ ] `python3 -m unittest discover -s tests` passes.
- [ ] If I changed display strings, I ran `python3 -m pipeline.i18n_extract` and committed the
      updated `i18n/en/catalog.en.json`.

## Clinician review (optional but gold)
- [ ] I am a clinician and have set `review.reviewedBy` / `review.reviewedOn`.
      Credentials / relevant specialty: <!-- e.g. GP, OB-GYN, NMC/GMC number if comfortable -->
