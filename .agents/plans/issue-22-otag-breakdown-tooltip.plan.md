# Plan: Otag/feature breakdown tooltip — top contributors to a card's Buzzword Score

## Summary
Add a hover tooltip on each scored card showing the **top ~5 features** (type / sub /
otag) that earned its Buzzword Score, with each contribution, sorted by magnitude. The
displayed score is already recomputed client-side in `filters.js`
(`recomputeScores`) from the `feature-weights` JSON, each card's `data-features`, and
the live `muted` set — so the tooltip is computed from those same inputs to stay
**consistent with the shown score** (including after Diagnostics mutes). The canonical
breakdown algorithm lives in `services/analysis.py` as a pure `score_breakdown` that
`score_card` delegates to (single source of truth, exercised server-side), and
`filters.js` mirrors it for the live tooltip — the same mirror pattern the file already
uses for `score_cards`. The empty tooltip element is injected by JS into each card's
`.card-info`, so there's no template/macro change and no clipping by
`.card-item { overflow: hidden }`.

## User Story
As a Brewer, I want to hover a Slept On card and see which features earned its score, so
that I understand and trust the recommendation.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW–MEDIUM |
| GitHub Issue | #22 |
| Systems Affected | `services/analysis.py`, `static/js/filters.js`, `static/css/style.css` |
| Dependencies | None — works on current code (`data-features` + `feature-weights` already rendered). Composes cleanly with #15/#17/#19/#21. |

---

## Spike Findings (from in-session code review)

- `score_card` (`services/analysis.py:154-160`) = `sum(weights[f] for f in
  card_features(card) if f in weights)`. No per-feature breakdown exists yet.
- The displayed score is **client-side**: `filters.js:25-34 recomputeScores()` sums
  `WEIGHTS[f]` over `data-features` minus the `muted` set, writing `data-score` + the
  `.js-score` span. So to reconcile with the *displayed* score, the tooltip must use the
  same client inputs (a server-rendered tooltip would go stale after a mute toggle).
- Both card grids already carry the needed data: `data-features="{{ card.features |
  join('|') }}"` (`commander.html:35`, `:62`) and the page-level
  `<script id="feature-weights">{{ feature_weights | tojson }}</script>`
  (`commander.html:118`), parsed into `WEIGHTS` at `filters.js:18-20`.
- Precedent for "JS mirrors analysis": `filters.js:15-17` comment "Mirrors
  services/analysis.score_cards".
- `.card-item { overflow: hidden; }` (`style.css:330-332`) would **clip** an absolutely
  positioned overlay → put the tooltip **in flow inside `.card-info`**, revealed on hover.
- `filters.js` already iterates `.card-item` (copy handler `:175-182`) and
  `.card-item[data-features]` (`:26`), so injecting a tooltip node per card fits.
- Feature kinds are `type:` / `sub:` / `otag:` (`analysis.py:37-60`); Diagnostics styles
  kind chips `.kind-otag` etc. (reusable look).

---

## Patterns to Follow

### Canonical scoring to refactor into a breakdown (single source of truth)
```python
# SOURCE: services/analysis.py:154-160
def score_card(card, weights):
    return sum(weights[f] for f in card_features(card) if f in weights)
```

### JS mirror of the analysis scoring (extend this idiom)
```javascript
// SOURCE: static/js/filters.js:15-34
// Mirrors services/analysis.score_cards: a card's score is the sum of the weights
// of the features it carries that are not currently muted.
const WEIGHTS = JSON.parse(document.getElementById('feature-weights')?.textContent || '{}');
const muted = new Set();
function recomputeScores() {
  document.querySelectorAll('.card-item[data-features]').forEach(card => {
    const feats = card.dataset.features ? card.dataset.features.split('|') : [];
    let sum = 0;
    feats.forEach(f => { if (!muted.has(f)) sum += WEIGHTS[f] || 0; });
    ...
  });
}
```

### Live-update hook to extend
```javascript
// SOURCE: static/js/filters.js:101-105
function rescore() { recomputeScores(); reorderSleptOn(); applyFilters(); }
```

### Existing kind-chip styling to echo
```css
/* SOURCE: static/css/style.css (kind-otag / kind-type / kind-sub chips in diagnostics) */
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/analysis.py` | UPDATE | Add pure `score_breakdown`; `score_card` delegates to it. |
| `static/js/filters.js` | UPDATE | Mirror breakdown; inject + populate per-card tooltips on load and on rescore. |
| `static/css/style.css` | UPDATE | `.score-tooltip` styling + hover reveal. |

No files created. No template change (tooltip node injected by JS).

---

## Tasks

Execute in order.

### Task 1: Expose the per-feature breakdown in analysis.py
- **File**: `services/analysis.py`
- **Action**: UPDATE
- **Implement**: Add a pure function and refactor `score_card` to use it:
  ```python
  def score_breakdown(card, weights, top_n=None):
      """
      The per-feature contributions behind a card's Buzzword Score: a list of
      (feature, contribution) for each feature the card carries that has a weight,
      sorted by absolute contribution descending. `top_n` truncates to the strongest
      contributors (None = all). Single source of truth shared with score_card and
      mirrored by static/js/filters.js for the hover tooltip.
      """
      contribs = [(f, weights[f]) for f in card_features(card) if f in weights]
      contribs.sort(key=lambda c: abs(c[1]), reverse=True)
      return contribs[:top_n] if top_n else contribs


  def score_card(card, weights):
      """Sum of the card's feature contributions (see score_breakdown)."""
      return sum(c for _, c in score_breakdown(card, weights))
  ```
  Keep `score_cards` (`:163-184`) unchanged — it still calls `score_card`.
- **Mirror**: `services/analysis.py:154-160`.
- **Validate**: `flake8 services/analysis.py && python -m py_compile services/analysis.py`;
  spot-check `score_card` output is unchanged for a sample card.

### Task 2: Inject + populate hover tooltips in filters.js
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**:
  1. Add a client mirror of `score_breakdown` (place near `recomputeScores`, after
     `WEIGHTS`/`muted` are defined at `:18-21`):
     ```javascript
     // Mirrors services/analysis.score_breakdown: top contributors to a card's
     // displayed score. Muted features contribute 0 and are dropped, so the list
     // reconciles with the (post-mute) score shown in .js-score.
     const TOOLTIP_TOP_N = 5;
     function topContributors(card, n = TOOLTIP_TOP_N) {
       const feats = card.dataset.features ? card.dataset.features.split('|') : [];
       return feats
         .map(f => [f, muted.has(f) ? 0 : (WEIGHTS[f] || 0)])
         .filter(([, w]) => w !== 0)
         .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
         .slice(0, n);
     }
     function featureLabel(f) {            // "otag:ramp" -> {kind:"otag", name:"ramp"}
       const i = f.indexOf(':');
       return { kind: f.slice(0, i), name: f.slice(i + 1) };
     }
     ```
  2. On load, inject one empty tooltip node into each scored card's `.card-info`:
     ```javascript
     document.querySelectorAll('.card-item[data-features]').forEach(card => {
       const info = card.querySelector('.card-info');
       if (info && !info.querySelector('.score-tooltip')) {
         const tip = document.createElement('div');
         tip.className = 'score-tooltip';
         info.appendChild(tip);
       }
     });
     ```
  3. Add `updateTooltips()` that fills each tooltip from `topContributors`:
     ```javascript
     function updateTooltips() {
       document.querySelectorAll('.card-item[data-features]').forEach(card => {
         const tip = card.querySelector('.score-tooltip');
         if (!tip) return;
         const rows = topContributors(card);
         tip.innerHTML = rows.length
           ? '<strong>Top contributors</strong>' + rows.map(([f, w]) => {
               const { kind, name } = featureLabel(f);
               return `<span class="tip-row"><span class="kind kind-${kind}">${kind}</span>`
                    + `${name}<span class="tip-val">${w >= 0 ? '+' : ''}${w.toFixed(3)}</span></span>`;
             }).join('')
           : '<em>No positive contributors</em>';
       });
     }
     ```
  4. Call `updateTooltips()` once on load (after injection + the initial
     `applyFilters()` at `:131`) and add it inside `rescore()` (`:101-105`) so mutes/
     re-ranks keep tooltips in sync.
  Leave the copy-on-click handler and all filters intact (the tooltip is display-only;
  clicking the card still copies its name).
- **Mirror**: `static/js/filters.js:25-34` (feature iteration), `:101-105` (rescore hook).
- **Validate**: page interaction (Task 4); `flake8` unaffected (no .py here).

### Task 3: Tooltip styling
- **File**: `static/css/style.css`
- **Action**: UPDATE
- **Implement**: Add a hover-revealed, in-flow tooltip that matches the dark palette:
  ```css
  /* ── Score breakdown tooltip (hover a card) ── */
  .score-tooltip {
    display: none;
    margin-top: 0.35rem;
    padding: 0.4rem 0.5rem;
    background: #0f3460;
    border: 1px solid #16213e;
    border-radius: 6px;
    font-size: 0.72rem;
    line-height: 1.4;
  }
  .card-item:hover .score-tooltip { display: block; }
  .score-tooltip strong { display: block; margin-bottom: 0.2rem; color: #aac4e8; }
  .score-tooltip .tip-row { display: flex; align-items: center; gap: 0.3rem; }
  .score-tooltip .tip-val { margin-left: auto; font-variant-numeric: tabular-nums; color: #e0e0e0; }
  ```
  Reuse the existing `.kind` / `.kind-otag|type|sub` chip classes already defined for the
  Diagnostics table (no new chip rules needed). If `.card-item { overflow: hidden }`
  visibly clips the expanded tooltip, the in-flow placement inside `.card-info` keeps it
  within the card's flow so it isn't cut off; verify in Task 4.
- **Mirror**: `static/css/style.css:330-355` (card/info styling), kind chips in the
  diagnostics block.
- **Validate**: visual (Task 4).

### Task 4: Manual smoke test
- **File**: n/a
- **Action**: verify
- **Implement**:
  1. `python app.py`, open `/commander/atraxa-praetors-voice`.
  2. Hover a high-scoring **Slept On** card → tooltip lists up to 5 features (kind chip +
     name + signed contribution), sorted by magnitude.
  3. Sanity: the listed contributions are consistent with the card's shown Score (the top
     few sum toward it; full sum equals the score when ≤5 features).
  4. Go to Diagnostics, mute a feature that appears in a card's tooltip → after the live
     rescore, that feature drops from the tooltip and the score updates in lockstep.
  5. Confirm hovering EDHRec-tab cards also shows the tooltip; clicking a card still
     copies its name.
- **Validate**: visual; tooltip matches the displayed score and reacts to mutes.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
python app.py   # hover Slept On cards on /commander/atraxa-praetors-voice
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Tooltip drifts from the displayed score after mutes/tag-rescore | Computed from the same `WEIGHTS` + `muted` + `data-features` as `recomputeScores`; `updateTooltips()` is called inside `rescore()`. |
| `.card-item { overflow: hidden }` clips an overlay tooltip | Tooltip is **in-flow inside `.card-info`** (expands the card on hover), not an absolute overlay. |
| Coupling to #17's card macro / template churn | Tooltip node is **injected by JS**, so no template/macro edit — works whether or not #17 has landed. |
| `score_card` refactor changes results | `score_breakdown` returns the same `(feature, weight)` terms `score_card` already summed; order doesn't affect the sum. Task 1 spot-checks parity. |
| Tooltip clutters dense grids | Only shown on hover; capped at `TOOLTIP_TOP_N = 5`. |

---

## Out of Scope (per issue)
- A full click-through panel listing *all* features (future enhancement). This is the
  compact top-N hover tooltip only.

---

## Acceptance Criteria

- [ ] Hovering a Slept On card shows a tooltip of the top contributing features
      (type/sub/otag), capped at 5, each with its contribution.
- [ ] Contributions sorted by magnitude and consistent with the displayed Buzzword Score
      (including after Diagnostics mutes).
- [ ] `services/analysis.py` exposes `score_breakdown` (single source of truth;
      `score_card` delegates to it).
- [ ] `flake8 .` clean; `py_compile` clean.
- [ ] Smoke test: a high-scoring Slept On card's tooltip aligns with its score.
- [ ] Follows CLAUDE.md (pure breakdown in analysis.py; JS mirrors it; display-only CSS).
- [ ] GitHub Issue #22 criteria satisfied.
```
