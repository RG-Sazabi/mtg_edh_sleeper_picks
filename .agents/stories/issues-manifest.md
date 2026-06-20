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
