# GitHub Issues Manifest

Generated from: .agents/PRDs/PRD.md
Date: 2026-06-19
Repository: RG-Sazabi/mtg_edh_sleeper_picks

| # | Issue | Title | URL |
|---|-------|-------|-----|
| 1 | #1 | Phase 1: Build EDHRec and Scryfall data pipeline | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/1 |
| 2 | #2 | Phase 2: Implement Buzzword Score engine (weighted otag TF analysis) | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/2 |
| 3 | #3 | Phase 3a: Build Flask app, routes, and Jinja2 templates | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/3 |
| 4 | #4 | Phase 3b: Add client-side filters and CSS styling | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/4 |
| 5 | #5 | Phase 4: Build static HTML export for GitHub Pages | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/5 |

## Batch 2 — Interactive scoring & search UX (added 2026-06-20)

Generated from: `.agents/PRDs/PRD.md` (Phase 5 / US-11–US-14)

| # | Issue | Title | URL |
|---|-------|-------|-----|
| 6 | #10 | Add Diagnostics feature toggles with live client-side re-scoring and re-ranking | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/10 |
| 7 | #11 | Show the feature-lift score on EDHRec-tab cards | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/11 |
| 8 | #12 | Add offline commander-name autocomplete to the search bar | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/12 |

## Batch 3 — EDHRec parity, broader-scope scoring & partner commanders (added 2026-06-20)

Generated from: `.agents/PRDs/prd-edhrec-parity-partners.md`

| # | Issue | Title | URL |
|---|-------|-------|-----|
| 9  | #15 | Fetch full per-commander EDHRec dataset: fix Slept On inclusion % and score on all-cards baseline | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/15 |
| 10 | #16 | Remove static export pipeline (export.py, docs/, freeze) and update docs | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/16 |
| 11 | #17 | Add New / High Synergy / Top display-only sections to the EDHRec tab | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/17 |
| 12 | #18 | Display searched commander header (image + name) at top of commander page | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/18 |
| 13 | #19 | Add bracket / budget / tag selectors with tag-aware Slept On rescoring | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/19 |
| 14 | #20 | Split diagnostics toggle into independent ignore-types / ignore-subtypes checkboxes | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/20 |
| 15 | #21 | Support partner commander pairings (partner / background / friends forever) | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/21 |
| 16 | #22 | Add otag/feature breakdown tooltip showing top contributors to a card's Buzzword Score | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/22 |

### Suggested sequencing (Batch 3)
1. **#15** — data foundation (full dataset, inclusion fix, all-cards scoring); unblocks #17, #19, #22.
2. **#16** — static-export removal; independent cleanup, any time.
3. **#17 / #18 / #20** — UI/parity; light dependence on #15, parallelizable.
4. **#19** — selectors + tag rescoring; builds on #15.
5. **#21** — partner pairings; coordinate header with #18.
6. **#22** — score-breakdown tooltip; after #15.

## Batch 4 — Type-segmented Slept On & Archidekt deck input (added 2026-06-22)

Generated from: `.agents/PRDs/prd-type-sections-archidekt.md`

| # | Issue | Title | URL |
|---|-------|-------|-----|
| 17 | #31 | Split Slept On into a Top 10 + per-card-type sections (server + template) | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/31 |
| 18 | #32 | Make filters and a shared N slider work across all Slept On sections (client) | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/32 |
| 19 | #33 | Add Archidekt deck-URL input: parse deck, detect commander, route to analysis | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/33 |
| 20 | #34 | Score Slept On against a linked deck: force 100% inclusion + "in deck" badge | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/34 |

### Suggested sequencing (Batch 4)
Two independent tracks that can proceed in parallel:
- **Type sections:** **#31** (server + template) → **#32** (client filtering / shared N slider).
- **Archidekt:** **#33** (deck ingestion + commander detection) → **#34** (deck-scoped scoring + "in deck" badge). #34 carries the key P_X/P_B scoring-formulation decision.

## Batch 5 — Tag-granularity controls for Slept On scoring (added 2026-06-28)

Generated from: `.agents/PRDs/prd-tag-granularity-controls.md`

| # | Issue | Title | URL |
|---|-------|-------|-----|
| 21 | #39 | Add oracle-tag hierarchy index (depth + level-N ancestors) to bulk.py | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/39 |
| 22 | #40 | Make scoring level-aware: cap oracle tags to a chosen depth + type/subtype toggle (analysis.py) | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/40 |
| 23 | #41 | Wire level + include-types controls through the commander route (app.py) | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/41 |
| 24 | #42 | Add named granularity selector + type toggle UI and sync diagnostics/tooltip | https://github.com/RG-Sazabi/mtg_edh_sleeper_picks/issues/42 |

### Suggested sequencing (Batch 5)
Strict dependency chain — build in order:
1. **#39** — tag hierarchy index (depth + level-N ancestors) in `bulk.py`; data foundation.
2. **#40** — level-aware feature generation (cap-at-N rollup + type toggle) in `analysis.py`.
3. **#41** — route wiring: read `?level` / `?include_types`, recompute weights server-side.
4. **#42** — named UI controls (Broad / Balanced / Fine) + diagnostics/tooltip sync.

Key decisions baked in: cap-at-level (no signal dropped) · keep-all level-N ancestors (DAG-safe) · types/subtypes off by default · functional-only (no `art_tags` toggle) · `cycle-*` retained (it's functional). Level names Broad/Balanced/Fine (depths 2/3/4) are an assumption — UI-only, rename freely.
