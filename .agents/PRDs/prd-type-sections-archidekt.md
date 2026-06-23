# Product Requirements Document
# Slept On — Type Sections & Archidekt Deck Input

**Version:** 1.0
**Date:** 2026-06-22
**Status:** Draft
**Builds on:** [PRD.md](PRD.md), [prd-edhrec-parity-partners.md](prd-edhrec-parity-partners.md)

---

## 1. Executive Summary

This PRD covers two incremental updates to the existing MTG EDH Sleeper Picks app. Both extend the current "Slept On" feature — they do not alter the underlying feature-lift scoring model (Ferrone 2026) already implemented in `services/analysis.py`.

**Update A — Type-segmented Slept On.** Today the Slept On tab is one flat grid of the top-N scored cards. This update splits the presentation into a single overall **Top 10** section plus seven **per-card-type** sections (Creatures, Instants, Sorceries, Enchantments, Artifacts, Lands, Planeswalkers). Each type section ranks cards independently within that type, so a card can appear in both the Top 10 and its type section(s). This lets the user scan sleeper picks by the slot they're trying to fill ("show me the slept-on creatures") instead of mentally filtering one long list.

**Update B — Archidekt deck input.** Today the only entry point is a commander name. This update adds a second input on the landing page that accepts an [Archidekt](https://archidekt.com/) deck URL. The app reads the deck list, detects its commander, and runs the existing Slept On pipeline — but treats every card actually in the deck as 100%-inclusion, so the scoring reflects what the *user's specific build* over-uses rather than the EDHRec average. Cards already in the deck still surface as picks, flagged with an "in deck" badge (mirroring today's "in EDHRec list" badge). The deck may be incomplete (fewer than 100 cards) and still works.

Both updates remain within the single-user, no-auth, locally hosted Flask architecture. No new persistence and no new third-party credentials are required.

---

## 2. Mission

**Mission Statement:** Make the Slept On signal easier to act on — sliceable by the deck slot you're filling, and tunable to your own decklist, not just the EDHRec average.

**Core Principles:**
1. **Same math, better lenses** — reuse the existing feature-lift scoring untouched; this is presentation + a new input source.
2. **Meet the user where the deck lives** — accept the deck list they already maintain on Archidekt.
3. **Graceful degradation** — partial decks, missing commanders, and unreachable URLs fail with a clear message, never a 500.
4. **Transparency preserved** — every card still shows its score and the Diagnostics breakdown still reconciles.
5. **No new infrastructure** — no database, no API keys, no background jobs.

---

## 3. Target Users

Unchanged from the base PRD: a single enthusiast Commander deckbuilder running the app locally, comfortable with Python/Flask and reading terminal output.

**New need addressed:** the user often has a real in-progress deck on Archidekt and wants sleeper suggestions tailored to *that* list, broken out by the card type they're shopping for, rather than re-deriving everything from the commander's metagame average.

---

## 4. MVP Scope

### In Scope

**Update A — Type Sections**
- [ ] A single **Top 10** Slept On section: the 10 highest-scoring picks overall (after active filters), fixed at 10.
- [ ] Seven per-type sections, each ranking its type independently: **Creatures, Instants, Sorceries, Enchantments, Artifacts, Lands, Planeswalkers**.
- [ ] Type sections rank independently of the Top 10 — a card may appear in both the Top 10 and its type section.
- [ ] Multi-type cards appear under every matching type section, **except creatures**: a creature (including an artifact/enchantment creature) slots **only** under Creatures; other multi-type cards still appear in every match (e.g. an artifact land under both Artifacts and Lands). _(Revised during #31 implementation — see Assumptions.)_
- [ ] A single **shared N slider** controls the card count shown in every type section uniformly (Top 10 is exempt — always 10).
- [ ] Existing filters (price cap, pauper toggle, inclusion cap) apply across the Top 10 and all type sections.
- [ ] Cards whose types fall outside the seven (e.g. a bare Battle, or Kindred-only) are simply absent from the type sections; they remain eligible for the Top 10.

**Update B — Archidekt Input**
- [ ] A second input on the landing page (`/`) accepting an Archidekt deck URL, alongside the existing commander search.
- [ ] Parse the deck ID from common Archidekt URL forms (`/decks/<id>`, `/decks/<id>/<slug>`).
- [ ] Fetch the deck via Archidekt's public deck API (no key required) in a new `services/archidekt.py`.
- [ ] Detect the deck's commander; if none can be determined, show a friendly error page (baseline depends on it).
- [ ] Fetch EDHRec data for the detected commander to supply the color-identity baseline, then force **inclusion = 100%** for cards present in the deck so scoring reflects the user's build.
- [ ] Render the same Slept On experience (Top 10 + type sections + Diagnostics) for the deck.
- [ ] Cards in the deck are **still suggested** as picks but tagged with an **"in deck"** badge.
- [ ] Works for incomplete decks (card count ≠ 100).

### Out of Scope (deferred)
- [ ] Per-section independent sliders (a single shared slider is the MVP).
- [ ] Deck sources other than Archidekt (Moxfield, Deckstats, plain text paste).
- [ ] Honoring Archidekt categories/maybeboard/companion semantics beyond commander detection.
- [ ] User-driven commander selection when detection is ambiguous (MVP errors instead).
- [ ] Persisting or caching fetched decks across runs.
- [ ] A "Battles" or "Kindred" type section.
- [ ] Splitting basic vs. nonbasic lands into separate sections (see Assumptions — basics are excluded by scoring).

---

## 5. User Stories

1. **As a deckbuilder, I want the Slept On picks split by card type, so that** I can quickly find sleeper cards for the exact slot I'm filling.
   *Example: I need card draw artifacts, so I jump straight to the Artifacts section instead of scrolling one long mixed list.*

2. **As a deckbuilder, I want one overall Top 10, so that** I can see the strongest sleepers at a glance regardless of type.
   *Example: The Top 10 surfaces a Planeswalker and two instants I'd never have scrolled to in a 50-card flat list.*

3. **As a deckbuilder, I want a card that is both an artifact and a creature to show in both sections, so that** I don't miss it when browsing either slot.
   *Example: Solemn Simulacrum shows under both Creatures and Artifacts.*

4. **As a deckbuilder, I want one slider to set how many cards each type section shows, so that** I can widen or tighten all sections at once.
   *Example: I drag the slider to 5 and every type section trims to its top 5.*

5. **As a deckbuilder, I want to paste my Archidekt deck URL, so that** I get sleeper picks tuned to my actual list rather than the metagame average.
   *Example: I paste my Atraxa superfriends list and the scoring leans harder into proliferate because my deck over-indexes on it.*

6. **As a deckbuilder, I want cards already in my deck to still appear but be marked "in deck", so that** I can see how my current cards rank without mistaking them for new suggestions.
   *Example: Doubling Season shows in the Enchantments section with an "in deck" badge.*

7. **As a deckbuilder, I want an incomplete deck to still work, so that** I can get suggestions while the deck is only 60 cards in.
   *Example: My 72-card draft still returns a full Slept On analysis.*

8. **As a deckbuilder, I want a clear error when my deck link has no detectable commander, so that** I understand why analysis can't run instead of seeing a crash.
   *Example: I paste a deck with no Commander category and get "Couldn't find a commander in that deck."*

---

## 6. Core Architecture & Patterns

Both updates fit the existing layered architecture (`app.py` routes → `services/*` → templates). No layer rule changes.

### Update A — Type Sections

**Where the split happens (recommended: server-side partition).** `services/analysis.py` already returns the full scored, sorted `slept_on` list. Add a pure helper there:

```
partition_by_type(slept_on, types) -> {type_name: [cards sorted by score desc]}
```

- Card → type membership is derived from the existing `card_features()` output (`type:Creature`, `type:Artifact`, …), so multi-type cards land in multiple buckets naturally.
- The route passes the Top 10 slice and the per-type buckets to the template; each renders its own `.card-grid`.
- Because a card can appear in multiple sections, its DOM node is duplicated per section. Keep the existing `SLEPT_ON_RENDER_CAP` budget per section so render stays bounded.

**Client filtering (`static/js/filters.js`).** Generalize the current single-grid logic so price/pauper/inclusion filters and the N-limit apply to *each* Slept On grid independently:
- Top 10 grid: N-limit fixed at 10.
- Type grids: N-limit = shared slider value.
- The Diagnostics live re-score/re-rank (`recomputeScores` / `reorderSleptOn`) must iterate all Slept On grids, not just `#slept-on-grid`. Duplicated nodes are already covered by the per-`.card-item[data-features]` recompute loop.

### Update B — Archidekt Input

**New service `services/archidekt.py`** (HTTP boundary, mirrors `edhrec.py` conventions — catches errors, returns `None`/empty rather than raising):
```
parse_deck_id(url) -> str | None
get_deck(url) -> {"commander_names": [str], "card_names": [str]} | None
```
- Uses Archidekt's public deck JSON endpoint (`https://archidekt.com/api/decks/<id>/`), no key.
- Commander detection: read the card(s) flagged with Archidekt's "Commander" category. Multiple → partner pairing (reuse `edhrec.resolve_pairing_slug`). Zero → return a sentinel the route turns into the friendly error.

**Route changes (`app.py`).**
- `/` POST gains an `archidekt_url` branch. If present, resolve the deck, detect the commander, and redirect to a deck-scoped commander view (e.g. `/commander/<slug>?deck=<id>`), or render the error page on failure.
- The commander view, when a `deck` is in play, joins the deck's card names onto the scoring path and forces `edhrec_inclusion = 1.0` for deck cards. Deck cards are flagged so the template renders the **"in deck"** badge; reuse the existing badge pattern (`in_edhrec` → add `in_deck`).

**Scoring integration — KEY DESIGN DECISION (see Risks §11).** The agreed direction: *EDHRec supplies the color-identity baseline; deck membership forces inclusion = 100% on the scoring set.* The exact P_X / P_B formulation (whether deck-forced inclusion feeds `compute_feature_stats` directly, or the baseline is computed from EDHRec's natural inclusion/synergy while deck presence drives P_X) is the single most important detail to nail down in the implementation plan. Two candidate formulations are listed in §11; the plan must pick one and document it in `analysis.py` alongside the existing model comment.

### Directory impact
```
services/archidekt.py        # NEW — deck URL → commander + card list
services/analysis.py         # + partition_by_type(); possibly generalized feature-stats inputs
app.py                       # + archidekt branch on /, deck scope on /commander
templates/index.html         # + archidekt URL input
templates/commander.html     # Top 10 + 7 type sections; "in deck" badge
static/js/filters.js         # multi-grid filtering + shared N slider + Top-10 fixed
static/css/style.css         # section headers / badge styling
```

---

## 7. Technology Stack

Unchanged from the base project. No new runtime dependencies anticipated.

| Technology | Version | Role in this PRD |
|---|---|---|
| Python | 3.12 | Runtime |
| Flask | 3.x | Routes for the new deck branch |
| Jinja2 | bundled | Top 10 + type-section templates |
| requests | existing | Archidekt deck fetch (same lib as `edhrec.py`) |
| pyedhrec / EDHRec JSON | existing | Commander baseline for deck scoring |
| Scryfall bulk store (`services/bulk.py`) | existing | Resolve deck card names → type_line + otags |

**Third-party integration (new):** Archidekt public deck API — read-only, anonymous, no key.

---

## 8. Security & Configuration

- **Auth:** none (unchanged — personal, local-only tool).
- **Environment variables:** none added.
- **External calls:** add Archidekt deck fetches. Apply the same defensive pattern as `edhrec.py` — timeout, `User-Agent` header, catch-and-return-`None`. Validate/parse the deck ID before requesting; ignore non-Archidekt URLs.
- **Input handling:** treat the deck URL as untrusted input — parse for a numeric deck ID, never interpolate the raw URL into a request path.
- **Security scope:** out of scope — rate-limit hardening, deck caching, and abuse prevention (single local user).

---

## 9. Success Criteria

**MVP success:** From the landing page the user can either (a) enter a commander and see the Slept On tab split into Top 10 + seven type sections, or (b) paste an Archidekt deck URL and get the same view scored against their own list with in-deck cards badged — both rendering without errors on a manual smoke test.

**Functional requirements:**
- [ ] Slept On tab shows a Top 10 section plus Creatures / Instants / Sorceries / Enchantments / Artifacts / Lands / Planeswalkers sections.
- [ ] A multi-type non-creature card appears in each matching type section (creatures slot only under Creatures) and, if it qualifies, the Top 10.
- [ ] The shared N slider resizes all type sections together; Top 10 stays at 10.
- [ ] Price cap, pauper toggle, and inclusion cap filter all sections correctly.
- [ ] Diagnostics feature toggles re-score and re-rank every section live, and scores reconcile with the tooltip breakdown.
- [ ] Pasting a valid Archidekt deck URL renders a full analysis; deck cards carry inclusion 100% and an "in deck" badge.
- [ ] An incomplete deck (≠100 cards) still renders a full analysis.
- [ ] A deck with no detectable commander renders the friendly error page, not a 500.

**Quality indicators:**
- [ ] `flake8 .` clean and `python -m py_compile` clean on all changed files (per CLAUDE.md Validation Sequence).
- [ ] `services/analysis.py` additions remain pure (no I/O); all HTTP stays in `services/archidekt.py`.
- [ ] No regression to the existing commander-name flow.

---

## 10. Implementation Phases

### Phase 1 — Type Sections (server + template)
**Goal:** Split the existing flat Slept On list into Top 10 + seven type sections, server-side.
**Deliverables:**
- [ ] `analysis.partition_by_type()` pure helper + unit-level reasoning in docstring.
- [ ] Route passes Top 10 slice + type buckets to the template.
- [ ] `commander.html` renders the eight grids with headers.
**Validation:** Atraxa renders all sections; a known artifact-creature appears in both Creatures and Artifacts; flake8/py_compile clean.

### Phase 2 — Type Sections (client filtering)
**Goal:** Make filters and the shared N slider work across all grids.
**Deliverables:**
- [ ] `filters.js` generalized to all Slept On grids; Top 10 fixed at 10, type grids on shared N.
- [ ] Diagnostics live re-score/re-rank iterates every grid.
- [ ] CSS for section headers.
**Validation:** Slider, price cap, pauper, inclusion cap, and Diagnostics mute all behave per-section in the browser.

### Phase 3 — Archidekt Ingestion
**Goal:** Turn a deck URL into a commander + card list.
**Deliverables:**
- [ ] `services/archidekt.py` (`parse_deck_id`, `get_deck`) with defensive error handling.
- [ ] Landing-page input + `/` POST branch; friendly error on no commander / fetch failure.
- [ ] Redirect into a deck-scoped commander view.
**Validation:** A real Archidekt URL resolves to the right commander and card names; a bad URL and a commander-less deck both show the error page.

### Phase 4 — Deck-Scoped Scoring & Badge
**Goal:** Force inclusion=100% for deck cards, badge them, and finalize the scoring formulation.
**Deliverables:**
- [ ] Chosen P_X/P_B formulation implemented and documented in `analysis.py`.
- [ ] `in_deck` flag + "in deck" badge in the template (reusing the `in_edhrec` pattern).
- [ ] Incomplete-deck handling verified.
**Validation:** Deck view scores differ from the bare-commander view in the expected direction; in-deck cards are badged; a 72-card deck renders fully; flake8/py_compile clean.

---

## 11. Risks & Mitigations

1. **Risk: The deck-scoring formulation is mathematically ambiguous.** Forcing `inclusion = 1.0` interacts non-trivially with the baseline `i_{c,B(X)} = inclusion − synergy` trick — naively setting inclusion to 1.0 while keeping EDHRec synergy corrupts the baseline.
   **Mitigation:** Treat this as the gating design task of Phase 4. Two candidate formulations to evaluate and choose between in the plan:
   - **(a) Baseline-from-EDHRec, presence-from-deck:** compute `P_B(f)` from EDHRec recommended cards' *natural* inclusion/synergy; compute `P_X(f)` from the deck (deck cards at inclusion 1.0). Generalize `compute_feature_stats` to accept distinct P_X and P_B card sets.
   - **(b) Override-in-place:** keep the existing single-set stats but, for cards that are both in the EDHRec set and the deck, override inclusion to 1.0; deck-only cards join the baseline from `inclusion_index` where available, else are dropped.
   Document the chosen formula next to the existing model comment in `analysis.py`.

2. **Risk: Archidekt commander detection is unreliable** (category naming, partners, backgrounds, companions).
   **Mitigation:** Detect via Archidekt's explicit "Commander" category; treat 2 commanders as a partner pairing through the existing `resolve_pairing_slug`; error cleanly on 0. Defer ambiguous-case user selection (out of scope).

3. **Risk: Duplicated DOM nodes across sections bloat the page** (a card in Top 10 + multiple type sections, times the render cap).
   **Mitigation:** Keep `SLEPT_ON_RENDER_CAP` per section; sections only need enough nodes to satisfy the max slider value after filtering. Measure node count on a 5-color commander.

4. **Risk: Archidekt API shape or URL format changes / endpoint unavailable.**
   **Mitigation:** Isolate all Archidekt specifics in `services/archidekt.py`; catch-and-return-`None` so the route shows the friendly error. Mirror the `pyedhrec`-breakage note in CLAUDE.md.

5. **Risk: Filter/re-score logic regresses the existing single-grid behavior** when generalized to many grids.
   **Mitigation:** Keep the commander-name flow as the baseline smoke test (Atraxa) after every phase; the flat-list behavior should be reproducible as "one grid" math applied per section.

---

## 12. Future Considerations

- **More deck sources:** Moxfield / Deckstats / plain-text paste behind the same "deck → commander + card list" interface.
- **Per-section sliders** and per-section collapse/expand for denser browsing.
- **Commander disambiguation UI** when Archidekt detection is ambiguous, replacing the hard error.
- **Deck-aware filters:** "hide cards already in my deck" toggle (the inverse of the in-deck badge).
- **Basic/utility land split** if the Lands section proves noisy.
- **Deck caching** keyed by deck ID + last-updated, if repeated lookups become common.

---

## Assumptions Made

- **As-built revision (#31, approved):** Creatures slot **only** under the Creatures section. An artifact/enchantment creature is treated as a creature (a creature is a creature to a deckbuilder) and is kept out of the Artifacts/Enchantments sections; other multi-type cards still appear under every matching section (e.g. an artifact land under both Artifacts and Lands). This intentionally overrides the original "appear in every matching section" requirement, at the user's direction. Also as-built: each section caps at `SLEPT_ON_SECTION_CAP` (100) drawn from the *full* scored list (replacing the planned global `SLEPT_ON_RENDER_CAP` of 200), and the per-grid filter/N-limit work originally scoped to #32 landed during #31.
- **Land basics:** Basic lands carry no discriminating features and score ~0 under the current model, so they will not appear in the Lands section without extra work; the Lands section effectively shows nonbasic/utility lands. Flagged rather than adding an explicit basic-land filter. (Confirm if undesired.)
- **Type set:** The seven sections are Creatures, Instants, Sorceries, Enchantments, Artifacts, Lands, Planeswalkers. Battle and Kindred/Tribal are intentionally excluded; such cards still compete for the Top 10. (Confirm.)
- **Top 10 reflects active filters:** the Top 10 = the 10 highest-scoring cards that pass the current price/pauper/inclusion filters (not a static pre-filter top 10), so toggling pauper doesn't leave hidden cards in the Top 10.
- **Deck-scoped routing:** the deck view is reachable as a query-scoped commander page (`/commander/<slug>?deck=<id>`) rather than a brand-new route, to reuse the existing pipeline. (Implementation detail; can change in the plan.)
- **Partner decks:** an Archidekt deck with two commanders routes through the existing partner-pairing slug logic.
