# Plan: Diagnostics Feature Toggles with Live Client-Side Re-Scoring

## Summary
Let the user mute card characteristics from the score directly in the Diagnostics tab —
a bulk "Ignore types & subtypes" toggle plus a per-row toggle for any individual feature —
and have the Slept On scores recompute and the grid re-rank **instantly in the browser**,
no page reload and no server call. We embed each Slept On card's feature list (`data-features`)
and the feature→weight map (a JSON `<script>` block) into the page, then extend the existing
client-side filter loop in `filters.js` to re-sum non-muted weights, rewrite each score,
re-sort the grid, and re-apply the existing N / inclusion / price / pauper filters. No Python
scoring logic changes — `services/analysis.py` stays pure; we only surface data it already
computes. Everything ships in the static export because it is pure client-side JS + embedded data.

## User Story
As a deckbuilder, I want to toggle off card characteristics in the Diagnostics tab — all
Type & Subtype features at once, or any individual feature — so that I can remove noise or
misleading signals and immediately see how the Slept On recommendations change.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | MEDIUM |
| GitHub Issue | #10 |
| Systems Affected | Frontend (templates, JS, CSS); thin route change in `app.py`; no change to `services/analysis.py` |

---

## Patterns to Follow

### Client-side filter loop (the thing we extend)
SOURCE: `static/js/filters.js:15-62` — `applyFilters()` reads `data-*` attributes off
`.card-item` nodes, toggles a `.hidden` class, and enforces the N-limit via a `visibleCount`
counter. New behavior must reuse this loop, not replace it. Listeners are wired at
`filters.js:55-59`; the page-load call is `filters.js:62`. The DOMContentLoaded guard
`if (!nSlider) return;` (`filters.js:10`) keeps this page-only.

### Card node shape (data attributes)
SOURCE: `templates/commander.html:29-34` — Slept On `.card-item` already carries
`data-name`, `data-price`, `data-rarity`, `data-inclusion`, `data-score`. We add `data-features`.
The visible score is `templates/commander.html:38` (`<span>Score: …</span>`).

### Diagnostics table rows
SOURCE: `templates/commander.html:84-104` — one `<tr class="weight-pos|neg">` per `feature_stats`
entry, with `{{ s.feature }}`, `{{ s.kind }}`, `{{ s.weight }}` available. We add a toggle cell
and a `data-feature` attribute here.

### Feature + weight source (already computed, do not duplicate)
SOURCE: `services/analysis.py:38-60` `card_features(card)` → `["type:Creature","sub:Elf","otag:…"]`;
`services/analysis.py:compute_feature_stats` → list of `{feature, kind, name, weight, …}`.
`app.py` already builds `weights = {s["feature"]: s["weight"] for s in feature_stats}` and passes
`feature_stats` to the template. Reuse both.

### CSS conventions
SOURCE: `static/css/style.css` — dark theme, accent `#e94560`, `.diag-table` (table),
`.kind-*` chips, `.card-item.hidden { display:none }`. New styles match this palette.

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `app.py` | UPDATE | Attach `features = analysis.card_features(c)` to each Slept On card; pass the `weights` map to the template as `feature_weights` |
| `templates/commander.html` | UPDATE | Add `data-features` + a JS-targetable score span to Slept On cards; embed `feature_weights` as a JSON `<script>`; add the bulk toggle control and per-row toggle + `data-feature` in the Diagnostics table |
| `static/js/filters.js` | UPDATE | Add muted-feature set, weight-map parse, `recomputeScores()`, `reorderSleptOn()`; wire bulk + per-row toggles; make `applyFilters()` iterate Slept On cards in current score order |
| `static/css/style.css` | UPDATE | Style the bulk toggle, per-row toggle, and muted-row state |

No change to `services/analysis.py` (stays pure) or `export.py` (embedded data + client JS already export cleanly).

---

## Design Notes / Decisions

- **Feature encoding**: `data-features="type:Creature|sub:Elf|otag:proliferate"`. Pipe `|` is a
  safe delimiter — feature slugs are `kind:name` with kinds `type|sub|otag` and names that are
  letters/digits/hyphens only (no `|`, no quotes). Built from `card_features` in `app.py`.
- **Weight map**: embed as `<script id="feature-weights" type="application/json">{{ feature_weights | tojson }}</script>`
  (a script block, not an attribute — avoids HTML-escaping pitfalls). JS does `JSON.parse(...)`.
- **Muting model**: JS keeps a `Set` of muted feature strings. A card's score = `Σ weights[f]` for
  `f` in its `data-features` **not** in the muted set. The bulk "Ignore types & subtypes" toggle
  mutes/unmutes every feature whose kind is `type:` or `sub:` (derived from the prefix — no extra
  data needed) and syncs the matching row checkboxes. Per-row toggles mute/unmute one feature.
- **Re-rank correctness**: after a re-score, `recomputeScores()` rewrites `data-score` + the visible
  span, `reorderSleptOn()` sorts `#slept-on-grid` children by `data-score` desc, then `applyFilters()`
  runs. To keep the N-limit picking the true top-N after re-sort, `applyFilters()` must iterate the
  Slept On cards in **current score order** (live-query the grid's children rather than the
  module-scoped NodeList captured at load). Initial server order is already score-desc, so first
  paint is unaffected.
- **Score display format**: JS writes `Score: ` + `value.toFixed(3)` to match the Jinja `round(3)`
  at `commander.html:38`.
- **Scope boundary with #11**: write `recomputeScores()` to update *any* `.card-item[data-features]`
  (so #11 only needs to add `data-features` + a score span to EDHRec cards). This issue only adds
  `data-features` to Slept On cards and only re-ranks `#slept-on-grid`.

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Surface features + weight map to the template
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**: In the `commander` route, after `slept_on` is built, attach
  `c["features"] = analysis.card_features(c)` to each Slept On card. Pass the existing `weights`
  dict to `render_template(...)` as `feature_weights=weights` (keep `feature_stats` too).
- **Mirror**: existing render call and the `weights` line in `app.py` (step 5 of the route).
- **Validate**: `.venv/Scripts/python.exe -m py_compile app.py`

### Task 2: Embed per-card features + weight JSON in the template
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: On the Slept On `.card-item` (`commander.html:29-34`) add
  `data-features="{{ card.features | join('|') }}"`. Give the score span a stable hook:
  `<span class="js-score">Score: {{ card.buzzword_score | round(3) }}</span>` (`commander.html:38`).
  Before the closing `{% endblock %}`, add
  `<script id="feature-weights" type="application/json">{{ feature_weights | tojson }}</script>`.
- **Mirror**: existing `data-*` attributes at `commander.html:29-34`.
- **Validate**: load check in Task 6 (template renders 200).

### Task 3: Add toggle controls to the Diagnostics table
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: Above the `.diag-table` (`commander.html:84`) add a bulk control:
  `<label><input type="checkbox" id="mute-types-subs"> Ignore types & subtypes</label>`.
  Add a leading `<th>` "On" to the header row and, in each body row (`commander.html:92-101`),
  a leading cell `<td><input type="checkbox" class="feature-toggle" checked
  data-feature="{{ s.feature }}"></td>`. Add `data-feature="{{ s.feature }}"` to the `<tr>`.
- **Mirror**: row structure at `commander.html:92-101`; control style at `#controls label`
  (`commander.html:7-10`).
- **Validate**: Task 6.

### Task 4: Implement live re-scoring in filters.js
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**:
  - Parse the weight map: `const WEIGHTS = JSON.parse(document.getElementById('feature-weights')?.textContent || '{}')`.
  - `const muted = new Set();`
  - `recomputeScores()`: for each `document.querySelectorAll('.card-item[data-features]')`, split
    `data-features` on `|`, sum `WEIGHTS[f] || 0` for `f` not in `muted`, set `dataset.score` and,
    if a `.js-score` child exists, set its text to `Score: ` + `sum.toFixed(3)`.
  - `reorderSleptOn()`: sort `#slept-on-grid` children by `parseFloat(dataset.score)` desc and
    re-append in order.
  - Refactor `applyFilters()` (`filters.js:15-53`) so the Slept On loop iterates
    `sleptOnGrid.querySelectorAll('.card-item')` (live, current DOM/score order) instead of the
    NodeList captured at `filters.js:13`; keep the price/pauper/inclusion + N-limit logic intact.
  - Wire toggles: `#mute-types-subs` change → add/remove every feature with prefix `type:`/`sub:`
    to `muted` and sync the matching `.feature-toggle` checkboxes; each `.feature-toggle` change →
    add/remove its `data-feature`. Both handlers end with
    `recomputeScores(); reorderSleptOn(); applyFilters();` and toggle a `.muted` class on the row.
- **Mirror**: `applyFilters` loop and listener wiring at `filters.js:15-62`.
- **Validate**: `node --check static/js/filters.js`

### Task 5: Style the toggles and muted rows
- **File**: `static/css/style.css`
- **Action**: UPDATE
- **Implement**: Accent-color the checkboxes (match `#controls input[type="checkbox"]`); add
  `.diag-table tr.muted { opacity: .45; }` with a strikethrough on the characteristic cell; style
  the `#mute-types-subs` label to sit above the table.
- **Mirror**: `#controls input[type="checkbox"] { accent-color:#e94560; }` and `.diag-table` rules.
- **Validate**: visual check in Task 6.

### Task 6: Verify end-to-end
- **File**: n/a
- **Action**: VERIFY
- **Implement**: `flake8 .`; start the app; load `/commander/atraxa-praetors-voice`; in Diagnostics,
  flip "Ignore types & subtypes" and an individual otag toggle; confirm Slept On scores change,
  the grid re-ranks, the N/price/pauper/inclusion filters still behave, and muted rows dim. Confirm
  no console errors. Spot-check that the embedded `#feature-weights` JSON and `data-features` are present.
- **Validate**: see Validation Sequence.

---

## Validation Sequence
```bash
.venv/Scripts/python.exe -m flake8 .
.venv/Scripts/python.exe -m py_compile app.py
node --check static/js/filters.js
# manual: run app.py, open the Atraxa page, exercise the toggles in Diagnostics
```

---

## Risks & Mitigations
| Risk | Mitigation |
|------|-----------|
| N-limit shows wrong cards after re-rank (stale NodeList order) | `applyFilters` iterates the grid's live children in current score order; `reorderSleptOn` runs before it |
| Feature string collides with the `\|` delimiter | Feature slugs are `kind:name` with no `\|`/quotes; safe. Keep the JSON weight map in a `<script>` block, not an attribute |
| Re-sort/recompute cost | ≤200 Slept On cards rendered (capped in `app.py`); trivial in JS |
| Breaking the static export | Logic is pure client-side JS + embedded data; `export.py` renders the same HTML, so it keeps working — verify by opening an exported page |
| Diverging score format vs server | JS uses `toFixed(3)` to match Jinja `round(3)` |

---

## Acceptance Criteria
- [ ] All tasks completed
- [ ] `flake8 .` passes; `py_compile` clean; `node --check` clean
- [ ] Bulk "Ignore types & subtypes" toggle mutes all `type:*`/`sub:*` features and re-ranks live
- [ ] Per-row toggle mutes/unmutes one feature and re-ranks live
- [ ] Slept On scores + ordering update with no page reload; N/inclusion/price/pauper still correct
- [ ] Muted rows visually distinguished
- [ ] Works when opened from the static export (no server)
- [ ] Follows existing patterns in `filters.js` / `commander.html`; `services/analysis.py` unchanged
- [ ] GitHub Issue #10 criteria satisfied
