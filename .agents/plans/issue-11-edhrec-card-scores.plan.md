# Plan: Show the Feature-Lift Score on EDHRec-Tab Cards

## Summary
EDHRec recommended cards are currently shown without our score (they're the exclusion set used
to build the lifts, not scored themselves). This adds the same inclusion-weighted feature-lift
score to every EDHRec-tab card — computed with the exact `weights` already built for the Slept On
section — displayed on the same scale, and updating live when the Diagnostics toggles (issue #10)
mute features. EDHRec cards stay grouped by category (we do **not** re-rank them); only the
displayed score is added. The work is one tiny pure helper in `services/analysis.py`, a short loop
in the route, and template attributes; the client-side re-score loop from #10 already updates any
card carrying `data-features`, so no new JS logic is needed.

## User Story
As a deckbuilder, I want to see our feature-lift score on the EDHRec recommended cards too, so that
I can compare how the app rates already-popular staples against the Slept On picks on the same scale.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW |
| GitHub Issue | #11 |
| Systems Affected | `services/analysis.py` (pure helper), `app.py` (route), `templates/commander.html` (EDHRec card markup) |
| Depends on | #10 (embeds `feature_weights` JSON + `recomputeScores()` over `.card-item[data-features]`) |

---

## Patterns to Follow

### Existing score computation (reuse, don't duplicate)
SOURCE: `services/analysis.py` `score_cards` — the per-card sum is
`sum(weights[f] for f in card_features(card) if f in weights)`. Extract that into a `score_card`
helper and reuse it for both Slept On and EDHRec cards.
SOURCE: `app.py:59-60` — `feature_stats = analysis.compute_feature_stats(edhrec_cards)` and
`weights = {s["feature"]: s["weight"] for s in feature_stats}` are already built before render.

### EDHRec card markup (where the score goes)
SOURCE: `templates/commander.html:55-67` — EDHRec `.card-item` carries `data-name`, `data-price`,
`data-rarity`, `data-inclusion` (no `data-score` yet) and a `.card-info` block with Synergy /
Inclusion / Price / rarity spans. The Slept On card is the template to mirror:
`templates/commander.html:34` (`data-score`) and `:38` (`<span class="js-score">Score: …</span>`,
the `.js-score` hook added by #10).

### Client re-score (already covers EDHRec once markup exists)
SOURCE: issue #10's `recomputeScores()` in `static/js/filters.js` iterates
`.card-item[data-features]` and rewrites each card's `data-score` + `.js-score` text. EDHRec cards
inherit this automatically once they carry `data-features` + a `.js-score` span. `reorderSleptOn()`
only touches `#slept-on-grid`, so EDHRec cards are **not** re-ordered — exactly what we want.

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/analysis.py` | UPDATE | Add a pure `score_card(card, weights)` helper; have `score_cards` call it (DRY) |
| `app.py` | UPDATE | After `weights` is built, attach `features` + `buzzword_score` to each EDHRec card |
| `templates/commander.html` | UPDATE | Add `data-features` + `data-score` + a `.js-score` "Score" span to the EDHRec `.card-item` |

No change to `static/js/filters.js` **assuming #10 is merged** (its `recomputeScores()` already
targets all `.card-item[data-features]`). See dependency note below.

---

## Design Notes / Decisions

- **Same score, same scale**: an EDHRec card's score is `Σ weights[f]` over its features
  (`analysis.card_features(card)`), skipping features not in `weights` (those below `min_support`).
  Identical formula to Slept On, so the two tabs are directly comparable. Scores may be negative or
  zero for EDHRec cards (unlike Slept On, which filters to `>0`); we display them as-is.
- **No re-ranking**: EDHRec stays grouped by `edhrec_category` (template `groupby` at
  `commander.html:51`). We only add a number; `reorderSleptOn()` deliberately scopes to
  `#slept-on-grid`.
- **Features attribute**: `data-features="{{ card.features | join('|') }}"` — same encoding as #10.
- **Dependency on #10**: this plan assumes #10 has landed (it embeds the
  `#feature-weights` JSON `<script>` and the `recomputeScores()`/listener wiring). If #11 is
  implemented **before** #10, also embed the weight map and add the recompute-on-toggle wiring
  here — but the recommended order is #10 → #11, so treat JS as unchanged and just verify EDHRec
  scores react to the toggles.
- **Score line placement**: add the Score span right after the card name, before Synergy, so the
  EDHRec card reads Score / Synergy / Inclusion / Price / Rarity (Score first, mirroring Slept On).

---

## Tasks

### Task 1: Extract a reusable per-card scorer
- **File**: `services/analysis.py`
- **Action**: UPDATE
- **Implement**: Add a pure function
  `def score_card(card: dict, weights: dict[str, float]) -> float: return sum(weights[f] for f in card_features(card) if f in weights)`.
  Refactor `score_cards` to call `score_card(card, weights)` instead of inlining the sum (behavior
  unchanged). Keep the module pure (no I/O).
- **Mirror**: the existing inline sum in `score_cards`.
- **Validate**: `.venv/Scripts/python.exe -m py_compile services/analysis.py`

### Task 2: Score the EDHRec cards in the route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**: After `weights = {...}` (`app.py:60`), loop the recommended cards:
  `for c in edhrec_cards: c["features"] = analysis.card_features(c); c["buzzword_score"] = analysis.score_card(c, weights)`.
  (Slept On cards get their `features` attached per issue #10's Task 1; this mirrors that for EDHRec.)
- **Mirror**: `app.py:57-63` scoring block; issue #10 Task 1.
- **Validate**: `.venv/Scripts/python.exe -m py_compile app.py`

### Task 3: Render the score on EDHRec cards
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: On the EDHRec `.card-item` (`commander.html:55-59`) add
  `data-features="{{ card.features | join('|') }}"` and
  `data-score="{{ card.buzzword_score }}"`. In its `.card-info` (`commander.html:61-67`), add
  `<span class="js-score">Score: {{ card.buzzword_score | round(3) }}</span>` immediately after the
  `<strong>{{ card.name }}</strong>` line.
- **Mirror**: Slept On card at `commander.html:34` and `:38`.
- **Validate**: Task 4 (renders 200, score visible).

### Task 4: Verify end-to-end
- **File**: n/a
- **Action**: VERIFY
- **Implement**: `flake8 .`; run the app; open `/commander/atraxa-praetors-voice`; on the EDHRec tab
  confirm each card shows a Score line on the same scale as Slept On; confirm EDHRec cards remain
  grouped by category (not re-ordered); in Diagnostics, mute a feature and confirm the EDHRec scores
  update live alongside Slept On; no console errors. Confirm an exported page (no server) shows the
  EDHRec scores.
- **Validate**: see Validation Sequence.

---

## Validation Sequence
```bash
.venv/Scripts/python.exe -m flake8 .
.venv/Scripts/python.exe -m py_compile app.py services/analysis.py
# manual: run app.py, open the Atraxa page, check EDHRec-tab scores + toggle reactivity
```

---

## Risks & Mitigations
| Risk | Mitigation |
|------|-----------|
| #10 not merged yet (no weight map / recompute loop) | Recommended order is #10 → #11; if reversed, also embed `#feature-weights` and the recompute wiring here |
| EDHRec scores unexpectedly negative/zero | Expected — EDHRec staples can under-represent features; display as-is, no `>0` filter |
| Accidentally re-ranking EDHRec cards | `reorderSleptOn()` is scoped to `#slept-on-grid`; EDHRec grids keep category `groupby` order |
| Double-attaching `features` (also set by #10) | #10 sets it on Slept On cards, #11 on EDHRec cards — disjoint sets; idempotent if both run |

---

## Acceptance Criteria
- [ ] All tasks completed
- [ ] `flake8 .` passes; `py_compile` clean
- [ ] Each EDHRec-tab card shows a feature-lift Score on the same scale/format as Slept On
- [ ] Score uses the same `Σ weight(f)` formula (`analysis.score_card`)
- [ ] EDHRec scores update live when Diagnostics toggles change (via #10's `recomputeScores`)
- [ ] EDHRec cards keep Synergy / Inclusion / Price / rarity and stay grouped by category (no re-rank)
- [ ] Works in the static export
- [ ] `services/analysis.py` stays pure; follows existing patterns
- [ ] GitHub Issue #11 criteria satisfied
