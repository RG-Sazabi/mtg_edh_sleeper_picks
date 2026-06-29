# Plan: Wire level + include-types controls through the commander route

## Summary
Read two new query params in `app.commander()` — `?level` (validated against the
named granularity levels, default **Balanced**) and `?include_types` (strict
boolean, default `false`) — and thread them into **every** scoring call so the
level/type-adjusted feature set drives the whole page consistently. The analysis
layer already accepts `level` / `include_types` as trailing kwargs (issue #40,
landed). This issue is route wiring only: parse the params once at the top of
`commander()`, pass them into `compute_feature_stats` + `score_cards` (which
produce the weights and the Slept On ranking) and into all `card_features(...)` /
`score_card(...)` enrichment call sites (EDHRec tab, featured rows, Slept On
diagnostics loop, deck tab) so diagnostics/tooltips never desync from the scores,
and surface the selected state to the template. It composes with the existing
`tag` / `budget` / `bracket` selectors because level/type apply to whatever
`scoring_cards` the tag scope already resolved. No UI controls and no `filters.js`
changes (separate UI issue).

## User Story
As a deck tuner, I want changing the level or type toggle to re-rank Slept On, so
that my granularity choice actually changes the recommendations.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW |
| GitHub Issue | #41 (depends on #40, landed) |
| Systems Affected | `app.py` (`commander()` route only); template context (display issue does the markup) |

---

## Context Facts (verified this session)

- **#40 is landed.** `services/analysis.py` exposes the constants and threaded
  params the route needs:
  - `LEVEL_DEPTHS = {"Broad": 2, "Balanced": 3, "Fine": 4}` and
    `DEFAULT_LEVEL = "Balanced"` ([services/analysis.py:62-63](services/analysis.py)).
  - `card_features(card, level=DEFAULT_LEVEL, include_types=False)`
    ([services/analysis.py:111-115](services/analysis.py)).
  - `compute_feature_stats(edhrec_cards, min_support=3, eps=1e-4, level=DEFAULT_LEVEL, include_types=False)`
    ([services/analysis.py:184-188](services/analysis.py)).
  - `score_card(card, weights, level=DEFAULT_LEVEL, include_types=False)`
    ([services/analysis.py:275-279](services/analysis.py)).
  - `score_cards(color_pool, weights, exclude_names, level=DEFAULT_LEVEL, include_types=False)`
    ([services/analysis.py:291-295](services/analysis.py)).
  - `partition_by_type(cards, cap=None)` reads types **toggle-independently**
    ([services/analysis.py:325](services/analysis.py)) — it takes **no** level/type
    params and must stay that way (it sections by raw type line, not the scoring
    toggle). **Do not pass level/include_types to it.**
- **All scoring call sites in `app.py` `commander()`** (grep-confirmed) that must
  receive the new settings:
  | Line | Call | Role |
  |------|------|------|
  | [app.py:213](app.py:213) | `compute_feature_stats(scoring_cards)` | builds `weights` |
  | [app.py:215](app.py:215) | `score_cards(color_pool, weights, exclude_names)` | Slept On ranking |
  | [app.py:221](app.py:221) | `card_features(c)` | EDHRec-tab features |
  | [app.py:222](app.py:222) | `score_card(c, weights)` | EDHRec-tab score |
  | [app.py:229](app.py:229) | `card_features(c)` | featured-row features |
  | [app.py:230](app.py:230) | `score_card(c, weights)` | featured-row score |
  | [app.py:257](app.py:257) | `card_features(c)` | Slept On `displayed` diagnostics loop |
  | [app.py:289](app.py:289) | `card_features(card)` | deck-tab features |
  | [app.py:290](app.py:290) | `score_card(card, weights)` | deck-tab score |
  - `partition_by_type` at [app.py:243](app.py:243) is intentionally **excluded**.
- **Existing scope-param pattern** is read-at-top, pass-through:
  `tag/budget/bracket/deck_id = request.args.get(...)` at
  [app.py:96-102](app.py:96), surfaced to the template as `selected_tag` /
  `selected_budget` / `selected_bracket` at [app.py:309-311](app.py:309). The
  template consumes those at [templates/commander.html:21-35](templates/commander.html)
  to mark `<option selected>`. `tag`/`budget`/`bracket` are passed to EDHRec
  un-validated (server trusts them); **`level` is different** — the PRD requires it
  validated against the known names with fallback to default
  (`.agents/PRDs/prd-tag-granularity-controls.md:235-237`).
- **Composition is automatic.** Level/type operate on `scoring_cards`, which the
  `tag` block at [app.py:139-148](app.py:139) already resolved (tag rescope →
  separate fetch; budget/bracket → base scoring view). So "theme tag + Fine" scores
  the tag-scoped cards at fine granularity with no extra wiring.

---

## Patterns to Follow

### Scope-param read at top of route (mirror for level/include_types)
```python
# SOURCE: app.py:96-102
tag = request.args.get("tag", "")
budget = request.args.get("budget", "")
bracket = request.args.get("bracket", "")
deck_id = request.args.get("deck", "")
```

### Validate against a known set with fallback to default (the new bit)
```python
# level must be a known name; anything else -> DEFAULT_LEVEL (PRD §Input handling)
level = request.args.get("level", "")
if level not in analysis.LEVEL_DEPTHS:
    level = analysis.DEFAULT_LEVEL
# strict boolean: only the literal "true" is True; absent/anything else -> False
include_types = request.args.get("include_types", "").lower() == "true"
```

### Selected scope surfaced to the template (mirror for selected_level/include_types)
```python
# SOURCE: app.py:309-311
selected_tag=tag,
selected_budget=budget,
selected_bracket=bracket,
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `app.py` | UPDATE | Parse `?level` (validated) + `?include_types` (strict bool) in `commander()`; thread both into the 9 scoring/feature call sites; pass `selected_level` + `include_types` to the template context. |

No new files. No template-markup changes (UI controls are the separate display issue);
this only adds the two context variables the markup will later consume.

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Parse `?level` + `?include_types` at the top of `commander()`
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**: In the "Scope selectors" block, just after `bracket = request.args.get("bracket", "")` ([app.py:98](app.py:98)), add the two new reads with a short comment explaining they re-score (not display-filter):
  ```python
  # Granularity controls (issue #41). Unlike budget/bracket these RE-SCORE: they
  # change the feature set, so they thread into compute_feature_stats + every
  # card_features/score_card call below (like `tag`). `level` is validated to a
  # known name (else default Balanced); `include_types` is a strict boolean.
  level = request.args.get("level", "")
  if level not in analysis.LEVEL_DEPTHS:
      level = analysis.DEFAULT_LEVEL
  include_types = request.args.get("include_types", "").lower() == "true"
  ```
- **Mirror**: `app.py:96-102` (scope reads), validation idiom above
- **Validate**: `python -m py_compile app.py`

### Task 2: Thread level/include_types into the weight + Slept On scoring calls
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  - [app.py:213](app.py:213): `feature_stats = analysis.compute_feature_stats(scoring_cards, level=level, include_types=include_types)`
  - [app.py:215](app.py:215): `slept_on = analysis.score_cards(color_pool, weights, exclude_names, level=level, include_types=include_types)`
  - **Do not** touch `partition_by_type(slept_on, cap=...)` at [app.py:243](app.py:243) — it takes no level/type params and sections toggle-independently by design.
- **Mirror**: kwarg style from `services/analysis.py` signatures
- **Validate**: `python -m py_compile app.py`

### Task 3: Thread level/include_types into the EDHRec-tab + featured enrichment loops
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  - EDHRec cards loop ([app.py:221-222](app.py:221)):
    - `c["features"] = analysis.card_features(c, level=level, include_types=include_types)`
    - `c["buzzword_score"] = analysis.score_card(c, weights, level=level, include_types=include_types)`
  - Featured cards loop ([app.py:229-230](app.py:229)):
    - `c["features"] = analysis.card_features(c, level=level, include_types=include_types)`
    - `c["buzzword_score"] = analysis.score_card(c, weights, level=level, include_types=include_types)`
- **Mirror**: Task 2 kwarg style
- **Validate**: `python -m py_compile app.py`

### Task 4: Thread level/include_types into the Slept On diagnostics loop + deck tab
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  - `displayed` diagnostics enrichment ([app.py:257](app.py:257)):
    - `c["features"] = analysis.card_features(c, level=level, include_types=include_types)`
  - Deck-tab loop ([app.py:289-290](app.py:289)):
    - `card["features"] = analysis.card_features(card, level=level, include_types=include_types)`
    - `card["buzzword_score"] = analysis.score_card(card, weights, level=level, include_types=include_types)`
  - **Verify after this task**: a repo-wide grep of `app.py` for `card_features(` and `score_card(` / `score_cards(` / `compute_feature_stats(` shows **every** occurrence now passes `level=level, include_types=include_types` (the AC's "every call site" / no-desync requirement), except `partition_by_type`.
- **Mirror**: Task 2 kwarg style
- **Validate**: `python -m py_compile app.py`

### Task 5: Surface selected level + type state to the template
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**: In the `render_template("commander.html", ...)` call, alongside `selected_tag` / `selected_budget` / `selected_bracket` ([app.py:309-311](app.py:309)), add:
  ```python
  selected_level=level,
  include_types=include_types,
  ```
  (The level selector + type toggle markup that consumes these is the separate UI issue; this only makes the state available so that issue is a pure-template change.)
- **Mirror**: `app.py:309-311`
- **Validate**: `python -m py_compile app.py`

---

## Validation Sequence

```bash
# From the project root.
python -m py_compile app.py
flake8 .
```

Then the CLAUDE.md manual smoke test — `python app.py`, search **"Atraxa,
Praetors' Voice"**, and exercise the new params directly on the URL (UI controls
land later), confirming no 500s and that rankings shift:

```
/commander/atraxa-praetors-voice                                  # default = Balanced + types off
/commander/atraxa-praetors-voice?level=Broad
/commander/atraxa-praetors-voice?level=Fine
/commander/atraxa-praetors-voice?include_types=true
/commander/atraxa-praetors-voice?level=Fine&include_types=true
/commander/atraxa-praetors-voice?level=Nonsense                   # falls back to Balanced (same as default)
/commander/atraxa-praetors-voice?tag=<a-real-tag-slug>&level=Fine # composes with tag rescope
```

Spot-check: `?level=Broad` vs `?level=Fine` produce a **different** Slept On
ranking and different `feature_stats`; `?level=Nonsense` renders identically to the
no-param default; the EDHRec-tab/featured/Slept On tooltip breakdowns stay
consistent with each card's score (same level/type used everywhere).

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Missing a `card_features`/`score_card` call site → diagnostics/tooltip desync from scores | Task 4 ends with an explicit grep audit of all `card_features(`/`score_card(`/`score_cards(`/`compute_feature_stats(` occurrences in `app.py`; the 9-row table in Context Facts is the checklist. |
| Accidentally passing level/type to `partition_by_type` (it takes neither) | Called out in Tasks 2 & Context Facts as intentionally excluded; passing them would be a `TypeError`. |
| Non-strict boolean lets odd values flip the toggle on | `include_types = request.args.get("include_types", "").lower() == "true"` — only the literal `true` is True; everything else (absent, `1`, `on`, garbage) is False, matching the PRD's "strict boolean, default false". |
| Invalid `level` reaching analysis | Route validates against `analysis.LEVEL_DEPTHS` and substitutes `DEFAULT_LEVEL` before any scoring call; `card_features` also defends internally, but the route is the AC's required gate. |
| Default render drifts from prior behavior | No params → `level="Balanced"`, `include_types=False` == the analysis defaults #40 already established, so the default page is byte-for-byte the current behavior. |

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] `commander()` reads `?level` validated against `analysis.LEVEL_DEPTHS` (falls back to **Balanced**) and `?include_types` as a strict boolean (default `false`)
- [ ] `level` / `include_types` passed into `compute_feature_stats` and **every** `card_features` / `score_card` / `score_cards` call site (EDHRec tab, featured, Slept On scoring + diagnostics loop, deck tab); `partition_by_type` left unchanged
- [ ] Weights + Slept On rankings recompute from the level/type-adjusted feature set; default render (no params) = Balanced + types excluded
- [ ] Composes with existing `tag` / `budget` / `bracket` selectors
- [ ] `selected_level` + `include_types` passed to the template context
- [ ] `flake8 .` clean; `python -m py_compile app.py` clean
- [ ] Manual smoke test ("Atraxa, Praetors' Voice") across all three levels and both toggle states with no 500s
- [ ] GitHub Issue #41 criteria satisfied
