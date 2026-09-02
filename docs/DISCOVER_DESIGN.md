# Discover — information architecture & interactions

*Discover* is the Softly app section this knowledge base feeds. It replaces the old accordion list.
It must feel like an **Apple experience**: elegant, calm, visual, lots of white space, very little
text — and **alive**, giving a reason to open Softly even on a day with nothing to log.

This doc defines the IA and interaction models so the KB is built to serve them. It lives in this
repo (not the app) because the KB's shape and this section's needs must stay in sync.

## Design principles
- **Image-first cards.** The illustration is the primary element; text is a short title + one line.
- **On-device & private.** Every "for you" signal is computed locally from the bundled KB + local
  logs. Nothing about what you read leaves the phone. (Trade-off we accept: no server-side tuning.)
- **Deterministic-but-fresh.** Daily content is seeded by `date + cycle phase + recent logs`, so it
  changes day to day yet is stable within a day and reproducible.
- **Graceful cold start.** A brand-new user with no data still sees a complete, curated Discover
  (editorial defaults), never empty "for you" slots.
- **Accessible by construction.** Full Dynamic Type + VoiceOver; every illustration has localized
  alt text; every card is a real, labelled control. "Very visual" must never mean "inaccessible."

## Home layout (top → bottom)
1. **Hero card** — one featured concept or path for the day. Large illustration, title, one line.
2. **Search** — a calm field. Full-text over titles + aliases + body, with per-language synonyms
   (users type "period pain," not "dysmenorrhea").
3. **Today's Question** — a single question with its answer directly below. Static, no quiz. Pulled
   from a `published` atom, chosen deterministically by date. Tapping it opens that atom.
4. **Continue learning** — resume the last atom / path opened, if any. Hidden when there's nothing.
5. **Today's insight** — a short, phase- or symptom-aware line linking to a relevant atom
   ("You're in your luteal phase — this is common now"). On-device. Hidden when no signal.
6. **Recommended for you** — a small rail of atoms chosen from `phases` + recently logged symptoms.
   Falls back to editorial picks on cold start.
7. **Categories** — the fixed taxonomy (`categories.yaml`), each a card with its hero illustration.
8. **Learning paths** — ordered sequences of atoms ("Understand your cycle in 5 steps").
9. **Keep exploring** — related atoms via the graph's `see-also` / `related-to` edges.

## Card types (all image-first)
- **Concept card** — illustration + title + `Glance` line → opens the atom.
- **Category card** — hero illustration + category title.
- **Path card** — illustration + title + progress (e.g. 2/5).
- **Question card** — question + answer, quieter styling.

## Atom (topic) page
Illustration header → `Overview` → (optional) `Deep` → **When to see a doctor** / **Red flags**
when present → **Related** (chips from the graph) → **Sources** (the citations, tappable). Calm,
scrollable, lots of air.

## What the KB must therefore provide (drives the schema)
- `Glance` for tooltips/insights; `Overview` for cards; `Deep` for the page → the **renditions**.
- `phases` + `type` → phase-aware recommendations and correct card rendering.
- `relations` → "Related" and "Keep exploring."
- `illustrationId` (+ category fallback + placeholder) → image-first everywhere.
- `sources` → the always-visible citations on the atom page.

## Illustration strategy (incremental, never blocking)
- **Category heroes first** (~10, from `categories.yaml`) — high impact, few.
- **Topic images** added over time. Until one exists, the card uses a **placeholder**: the
  category `colorToken` gradient + a simple symbol. Discover looks complete from day one.
- All illustrations **text-free** (so they localize), with **dark-mode variants** and **localized
  alt text**.

## Open interaction questions (decide during app build, not blocking the KB)
- Hero selection rule (featured path vs featured concept, and rotation).
- Whether paths track completion locally (they should, on-device).
- Motion budget for card entrances / transitions (respect Reduce Motion).
