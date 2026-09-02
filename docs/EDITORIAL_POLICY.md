# Editorial policy

This is how Softly Knowledge stays trustworthy **without an in-house clinician** — by never
being the medical authority itself. Softly is a **faithful, cited, localized summary layer** over
patient-education material published by recognised health authorities. Follow this policy and the
content is defensible; ignore it and it is not.

## 1. The core stance

- We do **not** author medical claims. We **summarise and cite** established public-health
  guidance. Think "Wikipedia for your cycle, but sourced only from tier-1 bodies."
- Content is **educational, never diagnostic or prescriptive.** No "you have X." No dosages, no
  treatment instructions, no "do this." Ever.
- Every atom traces back to a source a reader can open and check.

## 2. Allowed sources (tier-1 only)

Use these organisations. Prefer their **patient-education** pages over primary research.

| Org | Best for | Notes on reuse |
|-----|----------|----------------|
| **NHS** (Health A–Z) | plain-language conditions & symptoms | usually Open Government Licence (OGL) — reusable **with attribution** |
| **Office on Women's Health (OWH)** | women's-health fact sheets | US-gov, generally public domain — attribute anyway |
| **ACOG** | obstetrics/gynaecology patient FAQs | proprietary — **summarise in your own words**, cite, link |
| **WHO** | global fact sheets | CC BY-NC-SA / IGO terms — attribute, non-commercial-aware |
| **NICE** | UK clinical guidance (use the patient-facing summaries) | proprietary — summarise, cite |
| **ESHRE / FIGO** | fertility, reproductive medicine | proprietary — summarise, cite |
| **NCBI / PubMed** | last resort, background only | **do not interpret primary research**; only for uncontroversial, well-established facts already echoed by a patient-education source |

**Never:** blogs, forums, social media, commercial health sites, AI-generated medical claims,
or a single primary study interpreted by us. If only PubMed has it, it is probably too clinical
for Softly.

Each `sources[]` entry records `org`, `title`, `url`, `accessed` (the date a human last verified
the link *and* that it supports the claim), and `license`.

## 3. Copyright — original prose only

- **Write every sentence yourself.** Summarise the source's meaning in Softly's calm voice.
- **Never paste** source text, even one sentence. Different sources have different licences
  (see table); original summary + citation is the only safe path across all of them.
- Attribution is preserved per atom (the `sources` list) and repo-wide (`CONTENT_LICENSE.md`).

## 4. Safety rules (baked into the schema)

- Every `condition` and `symptom` atom should carry a **When to see a doctor** section.
- Concepts with urgent signs carry **Red flags** — unambiguous "seek urgent care if…" bullets.
  Softly Intelligence must **always surface a red flag** and never bury it under a softer message.
- A persistent, app-wide disclaimer and a first-run "education, not medical advice" screen are
  required in the app that consumes this KB.

## 5. Voice & tone

Calm, warm, plain, non-alarming, never clinical-cold, never cutesy. Second person, gentle.
Define any medical word in plain language the first time. Short sentences. No fear, no shame,
no judgement. Inclusive of all readers.

## 6. Review cadence & provenance

- Every atom has `review.nextReviewDue`. Medical info goes stale; the pipeline flags atoms past
  due so a decade-old base never silently rots.
- `review.reviewedBy` starts as `"unreviewed"`. That is honest and allowed — but:
  - **Ship the least controversial first:** anatomy, cycle physiology, phases, hormones.
  - Go deep on conditions (PCOS, endometriosis, etc.) **only** as review capacity grows.
  - Being open-source is the safety net: sources are public and checkable, and clinicians can
    review or contribute via pull requests. Actively invite that (`CONTRIBUTING.md`).
- Before Softly promotes Discover heavily, get at least one clinician to pass over the
  `condition` atoms.

## 7. What this policy is not

It does not make Softly a medical provider, and it does not make its authors liable clinicians.
It makes Softly a careful librarian of public-health guidance. Keep it that way.
