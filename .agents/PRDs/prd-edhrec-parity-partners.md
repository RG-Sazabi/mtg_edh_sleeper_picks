# PRD: EDHRec Parity, Broader-Scope Scoring & Partner Commanders

**Status:** Draft
**Date:** 2026-06-20
**Owner:** zanrick2@gmail.com
**Supersedes/Extends:** `.agents/PRDs/PRD.md` (original MTG EDH Sleeper Picks PRD)

---

## 1. Executive Summary

MTG EDH Sleeper Picks is a locally hosted Flask app that mirrors an EDHRec
commander page and adds a "Slept On" section surfacing underplayed cards with
high functional overlap to the recommended list, scored via a feature-lift model
over Scryfall oracle tags, card types, and subtypes.

This iteration closes the remaining gaps between our page and the real EDHRec
experience, fixes a correctness bug in how inclusion percentages are shown for
Slept On cards, and adds the most-requested PRD features (partner pairings and an
otag-contribution tooltip). It also broadens the scoring foundation: instead of
scoring against just the default-page cards, the Slept On model is built from the
commander's **full** EDHRec dataset, with tag selection able to re-focus the
model on a specific theme. Finally, it retires the now-discontinued GitHub Pages
static export, simplifying the app to a single local-Flask target.

**MVP goal:** Ship an EDHRec-faithful commander page — correct inclusion data,
New/High Synergy/Top sections, bracket/budget/tag selectors, partner pairings,
and a Buzzword-Score breakdown tooltip — with Slept On scoring grounded in the
commander's complete card data.

---

## 2. Mission

Help a Commander deck-builder find genuinely overlooked cards for their specific
commander (or pairing) by combining EDHRec's crowd data with a transparent,
feature-based "this fits your deck" score.

**Core principles:**
1. **Faithful to EDHRec** — if EDHRec shows it, we show it (parity in sections,
   filters, and data).
2. **Transparent scoring** — every Buzzword Score is explainable down to the
   features that produced it.
3. **Score the whole pool** — recommendations come from the commander's complete
   card data, not just the default page slice.
4. **Pure, layered computation** — scoring stays I/O-free in `services/analysis.py`;
   data fetching stays in `services/edhrec.py` / `services/scryfall.py`.
5. **Local-first simplicity** — personal-use Flask app; no auth, no static-export
   maintenance burden.

---

## 3. Target Users

**Primary persona — "The Brewer":** an experienced Commander player building or
tuning a deck for a specific commander. Comfortable with EDHRec terminology
(inclusion %, synergy %, brackets, budget, themes/tags). Runs the app locally via
`python app.py`. Wants to spot sleeper cards EDHRec's popularity sorting buries.

**Technical comfort:** High for MTG/EDHRec concepts; comfortable running a local
Python server. Not the audience for accounts, deploys, or cloud hosting.

**Key needs / pain points:**
- Trustworthy inclusion data (currently Slept On cards misleadingly show 0%).
- The same browsing surface as EDHRec (New/High Synergy/Top, brackets, budget,
  tags) without leaving the app.
- Theme-aware recommendations (rescore for a specific tag).
- Support for two-commander decks (partners/backgrounds/friends forever).
- Understanding *why* a card scored well.

---

## 4. MVP Scope

**In Scope:**
- [ ] **Fix Slept On inclusion %** — cross-reference the commander's full EDHRec
      dataset to populate `edhrec_inclusion` for Slept On cards; cards with no
      EDHRec data remain 0/unknown.
- [ ] **Split diagnostics toggles** — replace the single "Ignore types & subtypes"
      checkbox with two independent checkboxes (ignore types / ignore subtypes).
- [ ] **New / High Synergy / Top sections** — add these as display-only sections
      in the EDHRec tab (do not alter the scoring dataset).
- [ ] **Bracket / budget / tag selectors** — add controls mirroring EDHRec's
      scope options.
- [ ] **All-cards scoring baseline** — default Slept On scoring is built from the
      commander's complete EDHRec dataset, not the default page.
- [ ] **Tag-aware rescoring** — selecting a tag refetches that view and recomputes
      feature weights; bracket/budget act as display filters only.
- [ ] **Commander header** — display the searched commander (image + name) at the
      top of the page; show both for a pairing.
- [ ] **Partner commanders** — second autocomplete revealed when commander 1 is
      partner/background/friends-forever eligible, restricted to legal pairings;
      score from EDHRec's combined pairing page with the union color identity.
- [ ] **Otag breakdown tooltip** — on hover, show the top contributing features
      (type/sub/otag, capped, e.g. top 5) with each contribution.
- [ ] **Remove static export** — delete `export.py`, `docs/`, freeze logic, and
      related references; update `CLAUDE.md` guidance.

**Out of Scope (deferred):**
- [ ] Bracket/budget *rescoring* (they remain display filters this round).
- [ ] Multi-tag selection / arbitrary tag combinations (single tag only).
- [ ] Re-introducing any static/hosted deployment.
- [ ] Persisted user settings / accounts.
- [ ] Caching layers beyond the existing bulk store.

---

## 5. User Stories

1. **As a Brewer, I want Slept On cards to show their real inclusion %, so that I
   can trust the data instead of seeing a misleading 0%.**
   *Example:* For Atraxa, "Doubling Season" appears in Slept On showing the actual
   ~18% inclusion EDHRec reports, not 0%.

2. **As a Brewer, I want to ignore card types and subtypes independently in
   diagnostics, so that I can isolate how oracle tags alone drive the score.**
   *Example:* I check "ignore types" but leave subtypes on to see subtype-driven
   weights.

3. **As a Brewer, I want New / High Synergy / Top sections on the EDHRec tab, so
   that the page matches what I see on EDHRec.**
   *Example:* The "High Synergy" row shows the same top-synergy cards EDHRec
   highlights for my commander.

4. **As a Brewer, I want my Slept On recommendations scored against ALL of my
   commander's card data, so that fringe-but-relevant cards aren't excluded just
   because they're off the default page.**
   *Example:* A card outside the top default list still gets a meaningful Buzzword
   Score because the model saw the full dataset.

5. **As a Brewer, I want to pick a theme/tag and have Slept On rescore for it, so
   that I get recommendations tuned to my build.**
   *Example:* I select the "Superfriends" tag and the Slept On list reweights
   toward planeswalker-support features.

6. **As a Brewer, I want to filter the page by bracket and budget, so that I can
   browse the scope I care about — without my scores shifting underneath me.**
   *Example:* I switch to a budget view; the card lists filter but the Buzzword
   Scores stay anchored to the all-cards baseline.

7. **As a Brewer, I want to build a partner pairing, so that recommendations
   reflect both commanders.**
   *Example:* I pick "Tymna the Weaver", a second box appears, I add "Thrasios,
   Triton Hero", and Slept On scores from the combined WUBG pairing data.

8. **As a Brewer, I want to hover a Slept On card and see which features earned its
   score, so that I understand and trust the recommendation.**
   *Example:* Hovering "Smothering Tithe" shows top contributors like
   `otag:ramp`, `otag:treasure`, `type:Enchantment` with their weights.

---

## 6. Core Architecture & Patterns

Existing layered architecture is preserved; changes are additive within layers.

```
mtg_edh_sleeper_picks/
├── app.py                  # routes; add bracket/budget/tag + partner params
├── services/
│   ├── edhrec.py           # + full-dataset fetch, partner pairing page,
│   │                       #   bracket/budget/tag views, available-options query
│   ├── scryfall.py         # bulk-backed card attrs / color pool (union for pairs)
│   ├── bulk.py             # local Scryfall bulk store (unchanged)
│   └── analysis.py         # pure scoring; per-feature contributions for tooltip
├── templates/
│   ├── base.html
│   ├── index.html          # + conditional second commander autocomplete
│   └── commander.html      # + commander header, New/High/Top sections,
│                           #   bracket/budget/tag selectors, two diag checkboxes,
│                           #   tooltip markup
├── static/
│   ├── css/style.css       # tooltip + header + selector styling
│   └── js/filters.js       # selector wiring, tag-rescore fetch, tooltip behavior
├── requirements.txt
└── memory/
```

**Key patterns:**
- **Layer discipline (per CLAUDE.md):** `app.py` routes only; fetching in
  `edhrec.py`/`scryfall.py`; pure computation in `analysis.py`; templates display
  only.
- **Inclusion cross-reference:** build a `name -> edhrec_inclusion` map from the
  full dataset once per request and join it onto Slept On cards.
- **Scoring inputs vs. display inputs:** the feature-weight model consumes the
  all-cards (or selected-tag) dataset; New/High/Top and bracket/budget only affect
  what's rendered.
- **Per-feature contributions:** extend `score_card` to optionally return the
  `{feature -> contribution}` breakdown (reuse `compute_feature_stats` weights) so
  the tooltip and the score share one source of truth.
- **Pairing as first-class commander:** represent a pairing as a single logical
  commander (combined slug, union color identity) so downstream scoring is
  unchanged.

**Open technical detail (resolve in planning, not blocking):** the exact EDHRec
endpoint(s) for (a) the full per-commander card list, (b) the per-commander list
of available brackets/budgets/tags, and (c) the combined partner page slug format.
`services/edhrec.py` already talks to both `pyedhrec` and the raw
`json.edhrec.com/pages/commanders/<slug>.json` endpoint; the tag/budget/theme
variants are reachable via sibling JSON paths.

---

## 7. Technology Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| Flask | 3.x | Web server / routing |
| Jinja2 | bundled | Templating |
| pyedhrec | 0.0.2 | EDHRec commander/pairing/tag data (with raw-JSON fallback) |
| requests | latest | Raw EDHRec JSON endpoints |
| ijson | latest | Stream-parse Scryfall bulk files |
| Scryfall bulk (`default_cards`, `oracle_tags`) | local store | Card attrs, otags, color-identity pool |
| flake8 / black | latest | Lint / format |

**Removed this iteration:** Frozen-Flask / `export.py` static-export dependency
and the `/docs` output path.

**No new third-party integrations.** No API keys required.

---

## 8. Security & Configuration

- **Auth:** none — personal local-use app (unchanged).
- **Network:** outbound only to EDHRec (`json.edhrec.com`) and Scryfall bulk
  downloads; no inbound exposure beyond the local Flask dev server.
- **Config / env:** none required. Bulk store path stays `cache/` (gitignored);
  `default_cards`/`oracle_tags` refresh at 24h as today.
- **Security scope in:** graceful handling of EDHRec/Scryfall failures (return
  empty/`None`, render the friendly error page, never 500); no new attack surface.
- **Security scope out:** rate-limiting, auth, multi-user concerns — not
  applicable to a single-user local app.

---

## 9. Success Criteria

**MVP success:** Running `python app.py` and searching a commander (or pairing)
yields an EDHRec-faithful page where inclusion %s are correct, all new sections
and selectors work, partner pairings score correctly, and every Slept On card
explains its score on hover.

**Functional requirements:**
- [ ] Slept On cards display EDHRec's real inclusion %; cards with no data show
      0/unknown (consistent, not misleading).
- [ ] Diagnostics has two independent checkboxes; each toggles only its feature
      kind in the displayed weights.
- [ ] EDHRec tab renders New / High Synergy / Top sections with card data.
- [ ] Default Slept On scoring demonstrably uses the full dataset (more candidate
      cards than the default-page-only baseline).
- [ ] Selecting a tag changes the Slept On ordering/weights; switching bracket or
      budget changes displayed cards but NOT Buzzword Scores.
- [ ] Commander header shows image + name (both for pairings).
- [ ] A partner-eligible commander reveals a second autocomplete restricted to
      legal pairings; the resulting page scores from combined data + union color
      identity.
- [ ] Hovering a Slept On card shows up to ~5 top contributing features with
      weights.
- [ ] `export.py`, `docs/`, and freeze references are removed; app runs without
      them.

**Quality indicators:**
- [ ] `flake8 .` clean.
- [ ] `python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py` clean.
- [ ] Manual smoke test (Atraxa solo + a Tymna/Thrasios pairing) renders both
      sections with data.
- [ ] Tooltip contributions sum consistently with the displayed Buzzword Score.

---

## 10. Implementation Phases

### Phase 1 — Data correctness & cleanup
**Goal:** Fix the inclusion bug, broaden the scoring dataset, and retire static
export.
**Deliverables:**
- [ ] Full per-commander dataset fetch in `services/edhrec.py`.
- [ ] `name -> inclusion` cross-reference joined onto Slept On cards.
- [ ] Default scoring built from the full dataset.
- [ ] Remove `export.py`, `docs/`, freeze logic; update `CLAUDE.md`.
**Validation:** Slept On inclusion %s match the EDHRec tab; lint/compile clean;
app starts without export code.

### Phase 2 — EDHRec parity surface
**Goal:** Match EDHRec's browsing surface.
**Deliverables:**
- [ ] New / High Synergy / Top display-only sections.
- [ ] Commander header (single + pairing-aware).
- [ ] Bracket / budget / tag selectors (UI + route params).
- [ ] Bracket/budget as display filters; tag triggers rescore path.
- [ ] Split diagnostics checkboxes (ignore types / ignore subtypes).
**Validation:** Sections render; selectors filter/rescore as specified; both diag
checkboxes act independently.

### Phase 3 — Partner commanders
**Goal:** Two-commander pairings end to end.
**Deliverables:**
- [ ] Partner-eligibility detection + conditional second autocomplete (legal
      pairings only).
- [ ] Combined pairing page fetch; union color-identity pool.
- [ ] Pairing represented as a single logical commander through scoring.
**Validation:** A known pairing renders both commanders in the header and produces
a coherent Slept On list from combined data.

### Phase 4 — Transparency tooltip & polish
**Goal:** Explainable scores and final QA.
**Deliverables:**
- [ ] Per-feature contribution breakdown from `analysis.py`.
- [ ] Hover tooltip showing top ~5 contributors with weights.
- [ ] CSS/JS polish for header, selectors, tooltip.
- [ ] Full lint/compile + manual smoke test.
**Validation:** Tooltip contributions reconcile with the score; all success
criteria checked.

---

## 11. Risks & Mitigations

1. **EDHRec endpoint shape for full-dataset / tag / budget / pairing views is
   undocumented (pyedhrec 0.0.2 is unofficial).**
   *Mitigation:* Prototype the raw `json.edhrec.com` paths early in Phase 1; keep
   the existing requests-based fallback pattern; fail gracefully to the default
   page if a variant 404s.

2. **Cross-referenced inclusion still 0 for cards EDHRec genuinely lacks data on,
   confusing users.**
   *Mitigation:* Treat 0/unknown consistently and (optionally) style it distinctly;
   document that 0 = "no EDHRec data," not "never played."

3. **Bracket/budget filters being display-only may surprise users expecting their
   scores to change.**
   *Mitigation:* Make the scope-vs-score distinction visible in the UI (label that
   only tag rescores); deferred full rescoring is noted in Future Considerations.

4. **Partner pairing slug/legality rules are fiddly (background vs. partner-with vs.
   friends-forever).**
   *Mitigation:* Drive legal-pairing options from EDHRec/Scryfall data rather than
   hardcoding; restrict the second autocomplete to returned legal partners.

5. **Removing static export breaks any lingering references / muscle memory.**
   *Mitigation:* Grep for `export`, `freeze`, `docs/` references; update
   `CLAUDE.md` and architecture notes in the same change.

---

## 12. Future Considerations

- **Bracket/budget-aware rescoring** — let bracket/budget reshape the scoring
  baseline, not just the display.
- **Multi-tag / theme combinations** — score against intersections of themes.
- **Persisted preferences** — remember last bracket/budget/tag and filter settings.
- **Richer tooltip** — full breakdown panel (all features, not just top N) on click.
- **Three+ commander oddities / companion handling** if EDHRec exposes them.
- **Lightweight caching** of full-dataset fetches per commander within a session.

---

## Assumptions Flagged
- The combined EDHRec pairing page exposes cards/inclusion/synergy equivalently to
  a single-commander page (basis for "Use combined EDHRec page").
- EDHRec provides a per-commander list of available brackets/budgets/tags we can
  enumerate for the selectors; if not, we fall back to a known static set.
- "Top contributors" tooltip cap defaults to 5 (adjustable).
- `edhrec_inclusion = 0.0` remains the sentinel for "no EDHRec data."
