# Plan: Filters + shared N slider across all Slept On sections (client) — REVISED

> **Revised after partial delivery in #31.** The per-grid price/pauper/inclusion filtering
> and the per-type-section N-limit already shipped during #31. This plan covers only the
> **remaining** work. Verify the "already done" items rather than re-implementing them.

## Summary
`static/js/filters.js` already filters every `.slept-on-grid` and N-limits the seven type
sections. Four things remain to finish issue #32: (1) make the **Top 10 grid fixed at 10**
regardless of the slider (today it follows the slider, showing `min(slider, 10)`); (2) give
the Top 10 grid **filter-refill** so it always shows the 10 best cards that pass the active
filters (today it renders only 10 nodes and thins out); (3) generalize the Diagnostics
**re-rank** to every grid (today `reorderSleptOn` only re-sorts the Top 10 grid); and
(4) **hide empty type sections** + add the `.hidden-section` CSS. The Top 10 grid becomes
symmetric with a type section: it renders up to `SLEPT_ON_SECTION_CAP` candidates and is
N-limited to a fixed 10 via `data-fixed-n`. No scoring changes.

## User Story
As a deckbuilder, I want one slider to set how many cards each type section shows and all
filters to apply across every section, so that I can widen or tighten the whole Slept On
view at once — while the Top 10 always shows my 10 best usable picks.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW–MEDIUM (most of #32 already landed in #31) |
| GitHub Issue | #32 |
| Systems Affected | `static/js/filters.js` (primary), `templates/commander.html`, `app.py`, `static/css/style.css` |
| Depends on | #31 (shipped) |

---

## Current State (as-built)

**Already done (verify only):**
- `const sleptOnGrids = document.querySelectorAll('.slept-on-grid')` — `filters.js:29`.
- `applyFilters` (`filters.js:146-166`) applies price/pauper/inclusion to every grid and an
  N-limit (`visibleCount < maxN`) per grid. Type sections obey the shared slider correctly.

**Remaining (this plan):**
| # | Gap | Where |
|---|-----|-------|
| A | Top 10 follows the slider instead of being fixed at 10 | `filters.js:146-166` (uses `maxN` for all grids) |
| B | Top 10 can't refill — renders only 10 nodes | `commander.html:58-61` (`top_overall`, 10 cards); `app.py:175` |
| C | `reorderSleptOn` re-ranks only the single Top 10 grid | `filters.js:116-120`, called by `rescore` (`filters.js:185`) |
| D | Empty type sections show a bare `<h3>` | none — no hide logic |
| E | `.hidden-section` CSS absent | `static/css/style.css` |
| — | Misleading comment: "N limit only to the Top 10" (code does the opposite) | `filters.js:26-28` |

---

## Design Decisions

1. **Top 10 grid = a type-less section with a fixed N of 10.** It renders up to
   `SLEPT_ON_SECTION_CAP` (100) candidates — the same magnitude as each type section, so DOM
   cost is unchanged in order of magnitude — and JS caps it to 10 visible after filtering.
   This delivers refill (gaps B + A) with the existing machinery and no new constant.
   **Do NOT render the full `slept_on` list** (now unbounded — thousands of nodes on 5-color).
2. **`data-fixed-n` selects the per-grid N.** In `applyFilters`, `gridMaxN =
   grid.dataset.fixedN ? parseInt(...) : maxN`. Top 10 grid carries `data-fixed-n="10"`; type
   grids have none and use the slider. One code path, no id special-casing.
3. **Rename `top_overall` → `overall_pool`.** The variable now holds ~100 candidates, not 10;
   the "10" lives only in `data-fixed-n`. Renaming avoids a misleading name.
4. **Reorder every grid on rescore.** Generalize `reorderSleptOn` to iterate `sleptOnGrids`;
   the now-unused singular `sleptOnGrid` (`filters.js:25`) is removed.
5. **Hide empty sections once on load** (not re-evaluated on filter changes — keep simple).

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `templates/commander.html` | UPDATE | Top 10 grid loops `overall_pool` + `data-fixed-n="{{ top_overall_n }}"` |
| `app.py` | UPDATE | `overall_pool = slept_on[:SLEPT_ON_SECTION_CAP]`; pass `overall_pool` + `top_overall_n` |
| `static/js/filters.js` | UPDATE | Per-grid fixed-N in `applyFilters`; generalize reorder; hide empty sections; fix stale comment; drop unused singular handle |
| `static/css/style.css` | UPDATE | `.hidden-section { display: none; }` |

---

## Tasks

### Task 1: Top 10 grid renders a refillable pool, fixed at 10
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: Change the Top 10 grid (currently `{% for card in top_overall %}` over 10
  nodes) to loop the candidate pool and mark it fixed:
  ```jinja
  <h3>Top 10</h3>
  <div class="card-grid slept-on-grid" id="slept-on-grid" data-fixed-n="{{ top_overall_n }}">
    {% for card in overall_pool %}{{ slept_on_card(card) }}{% endfor %}
  </div>
  ```
  Leave the seven type-section grids and `#slept-on-controls` unchanged.
- **Mirror**: the type-section grid markup directly below it (`commander.html:62-67`).
- **Validate**: smoke test (Task 6).

### Task 2: Provide the Top 10 candidate pool from the route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  - Replace `top_overall = slept_on[:TOP_OVERALL_N]` (line 175) with
    `overall_pool = slept_on[:SLEPT_ON_SECTION_CAP]` (refill headroom; same cap as a type
    section). Keep `TOP_OVERALL_N = 10` — it now feeds the template's `data-fixed-n` only.
  - Update the `displayed = ...` enrichment union (line 184) to start from `overall_pool`
    instead of `top_overall` (the `id()` dedup already prevents double-enrichment).
  - In `render_template(...)`: replace `top_overall=top_overall` with
    `overall_pool=overall_pool` and add `top_overall_n=TOP_OVERALL_N`.
  - Refresh the comment block at lines 170-174 to describe the pool/fixed-N split.
- **Mirror**: existing kwargs at `app.py:193-208`.
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 3: Per-grid fixed-N + generalize re-rank in filters.js
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**:
  - **`applyFilters` (146-166):** choose the per-grid limit before the inner loop:
    ```javascript
    sleptOnGrids.forEach(grid => {
      const fixed = grid.dataset.fixedN;
      const gridMaxN = fixed ? parseInt(fixed, 10) : maxN;
      let visibleCount = 0;
      grid.querySelectorAll('.card-item').forEach(card => {
        // ...existing price/rarity/inclusion read + hiddenByFilters...
        if (hiddenByFilters) card.classList.add('hidden');
        else if (visibleCount < gridMaxN) { card.classList.remove('hidden'); visibleCount++; }
        else card.classList.add('hidden');
      });
    });
    ```
  - **`reorderSleptOn` (116-120):** reorder **every** grid; rename to `reorderSleptOnGrids`:
    ```javascript
    function reorderSleptOnGrids() {
      sleptOnGrids.forEach(grid => {
        const cards = Array.from(grid.querySelectorAll('.card-item'));
        cards.sort((a, b) => parseFloat(b.dataset.score) - parseFloat(a.dataset.score));
        cards.forEach(card => grid.appendChild(card));
      });
    }
    ```
  - **`rescore` (183-187):** call `reorderSleptOnGrids()`.
  - Remove the now-unused singular `const sleptOnGrid = document.getElementById('slept-on-grid');`
    (line 25) and correct the comment at 26-28 (it currently claims "N limit only to the Top
    10," the opposite of the code) to: filters + N-limit apply to every grid; the Top 10 grid
    is N-limited to a fixed 10 via `data-fixed-n`, the type grids to the shared slider.
- **Mirror**: existing per-grid loop in `applyFilters`; `recomputeScores` (99-108) stays as-is
  (already iterates all `.card-item[data-features]`).
- **Validate**: load page (Task 6) — no console errors.

### Task 4: Hide empty type sections on load
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**: After `sleptOnGrids` is defined and before the initial `applyFilters()` call,
  hide any grid with zero card nodes plus its preceding `<h3>`:
  ```javascript
  sleptOnGrids.forEach(grid => {
    if (grid.querySelectorAll('.card-item').length === 0) {
      grid.classList.add('hidden-section');
      const heading = grid.previousElementSibling;
      if (heading && heading.tagName === 'H3') heading.classList.add('hidden-section');
    }
  });
  ```
- **Mirror**: class-toggle hiding used throughout `filters.js`.
- **Validate**: a commander with an empty type bucket shows no bare header.

### Task 5: Add `.hidden-section` CSS
- **File**: `static/css/style.css`
- **Action**: UPDATE
- **Implement**: Add `.hidden-section { display: none; }` near `.card-item.hidden` (line 420).
  (Section `<h3>` headers already inherit the styled `h3` rule at line 190 — no extra header
  styling needed.)
- **Validate**: hidden sections fully collapse.

### Task 6: Validate + smoke test
- **File**: — (verification only)
- **Action**: VALIDATE
- **Implement**: Run the validation sequence, then `python app.py`, search
  "Atraxa, Praetors' Voice", Slept On tab, and confirm:
  - Dragging the N slider resizes **all seven type sections**; the **Top 10 stays at 10**
    (try N=3 and N=100 — Top 10 holds at 10).
  - A low price cap and/or pauper toggle filters every section, and the **Top 10 refills** to
    10 cheaper/common cards instead of thinning out.
  - Inclusion-cap slider filters all sections.
  - Diagnostics "ignore types" re-scores and **re-ranks every section** live; visible top-N
    per section updates; scores reconcile with the hover tooltip.
  - No empty section headers; tabs switch and click-to-copy work (no JS crash).
- **Validate**: see Validation Sequence.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py
# Manual smoke (per CLAUDE.md): python app.py -> search "Atraxa, Praetors' Voice"
#   exercise N slider (3 and 100), price cap, pauper, inclusion cap, Diagnostics mutes
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Rendering too many Top 10 nodes (full `slept_on` is unbounded) | Cap the pool at `SLEPT_ON_SECTION_CAP` (100), same as a type section; never loop the full list. |
| `data-fixed-n` missing/typo'd → Top 10 follows the slider again | Task 6 explicitly checks Top 10 holds at 10 at N=3 and N=100. |
| Renaming `top_overall` misses a reference | grep `top_overall` across `app.py` + `templates/` after Task 2; only the route + template use it. |
| Reorder-all interacts badly with fixed-N Top 10 | Same iterate-live-children approach as the type grids; smoke-test Diagnostics re-rank on Top 10 + a type section. |

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] `flake8 .` clean; `python -m py_compile app.py` clean
- [ ] No test suite (per CLAUDE.md) — manual Atraxa smoke test passes
- [ ] GitHub Issue #32 criteria satisfied:
  - [ ] Shared N slider sizes every type section uniformly; **Top 10 fixed at 10** (slider-independent)
  - [ ] Price cap, pauper, and inclusion cap filter the Top 10 and all type sections *(already shipped in #31 — verify)*
  - [ ] Top 10 reflects active filters — refills to the top 10 that pass; no hidden cards in it
  - [ ] Diagnostics toggles re-score and **re-rank every section** live; scores reconcile with the tooltip
  - [ ] No regression to the single-section / commander-name flow

---

## Out of Scope
- Per-section independent sliders
- Server-side partitioning / section structure (owned by #31, shipped)
- Archidekt deck input and the "in deck" badge (#33 / #34)
