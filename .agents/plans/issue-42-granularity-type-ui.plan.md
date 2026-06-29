# Plan: Named granularity selector + type toggle UI, synced diagnostics/tooltip

## Summary
Surface the granularity controls that issue #41 already wired through the route.
Add a **named** level selector (**Broad / Balanced / Fine**, default Balanced, no
numbers) and an **"Include card types & subtypes"** checkbox (default off) to the
`#controls` bar in `templates/commander.html`, reflecting the `selected_level` /
`include_types` context vars #41 already passes. The level `<select>` reuses the
existing `select[data-param]` change→reload handler verbatim; the checkbox needs a
small new reload handler in `static/js/filters.js` (it sets/clears `?include_types`).
Because #41 already threads level/type into **every** `card_features` call, each
card's emitted `data-features` is already level-capped and the tooltip
(`topContributors`) already consumes that list verbatim against the level-correct
`feature-weights` — so the diagnostics table and hover tooltip are **already** in
sync once the controls exist. This issue is therefore a focused template + one-JS-
handler change plus a verification pass that no independent leaf-tag expansion
remains in JS.

## User Story
As a deck tuner, I want named granularity controls on the commander page and a
trustworthy "why did this score" view, so that I can tune the signal and understand
the result without numbers or code.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW |
| GitHub Issue | #42 (depends on #41, landed) |
| Systems Affected | `templates/commander.html` (controls markup), `static/js/filters.js` (checkbox reload handler); no Python/route changes |

---

## Context Facts (verified this session)

- **#41 is fully landed.** The route already:
  - parses `?level` (validated against `analysis.LEVEL_DEPTHS`, fallback
    `DEFAULT_LEVEL`) and `?include_types` (strict bool) at
    [app.py:103-106](app.py:103);
  - threads both into every `compute_feature_stats` / `card_features` /
    `score_card` / `score_cards` call (grep-confirmed: app.py lines 222, 226, 234,
    237, 246, 249, 278, 312, 315);
  - passes `selected_level=level` and `include_types=include_types` to the template
    at [app.py:338-339](app.py:338).
  - **No route/analysis change is needed for this issue.**
- **Level constants** live in analysis: `LEVEL_DEPTHS = {"Broad": 2, "Balanced": 3,
  "Fine": 4}`, `DEFAULT_LEVEL = "Balanced"`
  ([services/analysis.py:62-63](services/analysis.py)). The UI shows the **names**
  only (the keys), never the depths.
- **`data-features` is already emitted, already level-capped.** Both card macros
  render `data-features="{{ card.features | join('|') }}"`
  ([templates/_card.html:8](templates/_card.html),
  [templates/_card.html:29](templates/_card.html)); `card["features"]` is populated
  by `analysis.card_features(..., level=level, include_types=include_types)` in the
  route, so the list is already the chosen level's capped feature set.
- **The tooltip already consumes server features verbatim — no leaf expansion.**
  `topContributors` reads `card.dataset.features.split('|')` and maps each to
  `WEIGHTS[f]` ([static/js/filters.js:54-61](static/js/filters.js)); `WEIGHTS`
  comes from the `feature-weights` JSON
  ([static/js/filters.js:45-47](static/js/filters.js)), which is
  `feature_weights | tojson` from `compute_feature_stats` at the chosen level
  ([templates/commander.html:138](templates/commander.html)). There is **no**
  independent tag-hierarchy expansion in JS. ⇒ AC "tooltip matches server" and "no
  leaf-tag rows for tags the card no longer scores on" hold structurally once the
  controls exist; this issue verifies, it does not rewrite the tooltip.
- **Existing scope-selector pattern** ([templates/commander.html:16-41](templates/commander.html)):
  each `<select>` carries `data-param="..."` and marks the active `<option>` with
  `{{ 'selected' if X == selected_Y }}`. The change→reload handler at
  [static/js/filters.js:15-22](static/js/filters.js) handles **`select[data-param]`
  only** (reads `sel.value`); it does **not** catch checkboxes.
- **The `scope-note`** at [templates/commander.html:40](templates/commander.html)
  currently says only Theme re-scores. It must be updated: **Theme, Level, and
  Include-types all re-score**; Budget & Bracket are display-only.
- **Distinct from the Diagnostics mute toggles.** The Diagnostics tab has
  client-only "Ignore types / Ignore subtypes" display mutes
  ([templates/commander.html:108-111](templates/commander.html),
  `bindKindMute` at [static/js/filters.js:208-223](static/js/filters.js)). The new
  "Include card types & subtypes" control is a **server recompute** (changes the
  scored feature set), not a display mute — the AC requires the UI to make this
  distinction clear.
- **CSS already covers the new controls.** `#controls label` flex layout, default
  `<select>` styling, and `#controls input[type="checkbox"]`
  ([static/css/style.css:180-198](static/css/style.css)) all apply; **no CSS
  changes are required.**

---

## Patterns to Follow

### Scope `<select>` with data-param + selected option (mirror for Level)
```html
<!-- SOURCE: templates/commander.html:25-31 (Budget selector) -->
<label>Budget:
  <select id="budget-select" data-param="budget">
    <option value="">Any</option>
    <option value="budget"    {{ 'selected' if selected_budget == 'budget' }}>Budget</option>
    <option value="expensive" {{ 'selected' if selected_budget == 'expensive' }}>Expensive</option>
  </select>
</label>
```

### Existing select change→reload handler (Level reuses this as-is; checkbox needs its own)
```js
// SOURCE: static/js/filters.js:15-22
document.querySelectorAll('select[data-param]').forEach(sel => {
  sel.addEventListener('change', () => {
    const url = new URL(window.location.href);
    if (sel.value) url.searchParams.set(sel.dataset.param, sel.value);
    else url.searchParams.delete(sel.dataset.param);
    window.location.assign(url.toString());
  });
});
```

### Checkbox in #controls (mirror markup for the type toggle)
```html
<!-- SOURCE: templates/commander.html:39 (Pauper toggle) -->
<label><input type="checkbox" id="pauper-toggle"> Pauper only (commons)</label>
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `templates/commander.html` | UPDATE | Add Level `<select data-param="level">` (Broad/Balanced/Fine, `selected_level`) and an "Include card types & subtypes" checkbox (`include_types`) to `#controls`; update the `scope-note` to list Level + Include-types as re-scoring controls. |
| `static/js/filters.js` | UPDATE | Add a change handler for the include-types checkbox that sets `?include_types=true` (or deletes the param when unchecked) and reloads, mirroring the existing select handler. Add a clarifying comment confirming the tooltip consumes server `data-features` verbatim (no leaf expansion). |

No new files. No Python, route, or CSS changes.

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Add the named Level selector to `#controls`
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: Inside `#controls`, after the Bracket `<label>` block
  ([templates/commander.html:32-37](templates/commander.html)) and before the
  Max-price input, add a Level selector. Names only — **no numbers**. Default
  Balanced is enforced server-side, but mark the active option from
  `selected_level`:
  ```html
  <label>Level:
    <select id="level-select" data-param="level">
      <option value="Broad"    {{ 'selected' if selected_level == 'Broad' }}>Broad</option>
      <option value="Balanced" {{ 'selected' if selected_level == 'Balanced' }}>Balanced</option>
      <option value="Fine"     {{ 'selected' if selected_level == 'Fine' }}>Fine</option>
    </select>
  </label>
  ```
  All three options carry a non-empty `value`, so the existing
  `select[data-param]` handler always `set`s `?level` on change (no "clear" case) —
  matching the route's validated, always-defined level.
- **Mirror**: [templates/commander.html:25-31](templates/commander.html) (Budget
  select markup + `selected_*` idiom)
- **Validate**: visual — option count = 3, names only, no depth integers in markup.

### Task 2: Add the "Include card types & subtypes" server-recompute toggle
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: After the new Level selector, add a checkbox whose checked state
  reflects `include_types`. Give it a stable id for the JS handler and a tooltip
  that distinguishes it from the Diagnostics display mutes:
  ```html
  <label title="Re-scores using card types &amp; subtypes as features (server recompute). Distinct from the Diagnostics tab's display-only Ignore types/subtypes.">
    <input type="checkbox" id="include-types-toggle" {{ 'checked' if include_types }}>
    Include card types &amp; subtypes
  </label>
  ```
- **Mirror**: [templates/commander.html:39](templates/commander.html) (Pauper
  checkbox markup)
- **Validate**: visual — checkbox present, reflects `include_types`, default off.

### Task 3: Clarify the scope-note (which controls re-score vs. re-scope)
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: Replace the `scope-note` text at
  [templates/commander.html:40](templates/commander.html) so it names the
  re-scoring controls now that Level + Include-types join Theme:
  ```html
  <p class="scope-note"><strong>Theme</strong>, <strong>Level</strong>, and
    <strong>Include card types &amp; subtypes</strong> re-score Slept On;
    Budget &amp; Bracket re-scope the displayed cards only. (The Diagnostics tab's
    Ignore-types/subtypes toggles only mute the display — they don't re-score.)</p>
  ```
- **Mirror**: existing `scope-note` paragraph (same class, same location)
- **Validate**: visual — note reads correctly; no stray markup.

### Task 4: Add the include-types checkbox reload handler in filters.js
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**: Immediately after the `select[data-param]` handler block
  ([static/js/filters.js:15-22](static/js/filters.js)), add a dedicated handler for
  the type toggle. It mirrors the select handler (server recompute via full reload),
  but reads `.checked` and uses the literal `"true"` the route's strict-boolean
  parse expects:
  ```js
  // ── Include-types toggle: a SERVER recompute (changes the scored feature set),
  // not a display mute. Checked -> ?include_types=true and reload; unchecked ->
  // drop the param (route default is types-off). Distinct from the Diagnostics
  // tab's client-only "Ignore types/subtypes" mutes (bindKindMute below).
  const includeTypesToggle = document.getElementById('include-types-toggle');
  if (includeTypesToggle) {
    includeTypesToggle.addEventListener('change', () => {
      const url = new URL(window.location.href);
      if (includeTypesToggle.checked) url.searchParams.set('include_types', 'true');
      else url.searchParams.delete('include_types');
      window.location.assign(url.toString());
    });
  }
  ```
  Place it before the `edhrecCards` query (line 24) so it sits with the other
  scope-reload wiring, above the live-filter logic.
- **Mirror**: [static/js/filters.js:15-22](static/js/filters.js) (select reload
  handler — same URL/reload approach)
- **Validate**: `node -e "void 0"` not required; rely on the page smoke test. Ensure
  the guard (`if (!nSlider) return;` at line 10) still precedes this — it does, so
  the handler only binds on the commander page.

### Task 5: Confirm + comment that the tooltip consumes server features verbatim
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**: **No logic change.** `topContributors`
  ([static/js/filters.js:54-61](static/js/filters.js)) already scores only from
  `card.dataset.features` against `WEIGHTS`, with no tag-hierarchy expansion — which
  is exactly the AC's requirement now that the server emits level-capped `features`.
  Tighten the existing comment above `topContributors` (lines 50-53) to state the
  level-sync invariant explicitly, e.g.:
  ```js
  // Mirrors services/analysis.score_breakdown: top contributors to a card's
  // displayed score, scored ONLY from the card's server-emitted (already
  // level/type-capped, issue #41/#42) data-features against the level's WEIGHTS.
  // No leaf-tag expansion here, so the tooltip can't list a tag the card no
  // longer scores on at the current level. Muted features contribute 0 and drop.
  ```
- **Mirror**: existing comment style at
  [static/js/filters.js:42-53](static/js/filters.js)
- **Validate**: re-read `topContributors` + `recomputeScores` to confirm neither
  expands tags beyond `data-features`.

### Task 6: Validation + manual smoke test
- **File**: — (no file change)
- **Action**: VALIDATE
- **Implement**: Run the validation sequence below, then the manual smoke test.
- **Validate**: see next section.

---

## Validation Sequence

```bash
# From the project root. (No Python changed, but run the project's standard gate.)
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
```

Then the CLAUDE.md manual smoke test — `python app.py`, search **"Atraxa,
Praetors' Voice"**, and exercise the new controls from the UI (not just the URL):

1. **Default render**: Level selector shows **Balanced** selected; "Include card
   types & subtypes" **unchecked**. URL has no `?level`/`?include_types`.
2. **Change Level** Broad → Balanced → Fine via the dropdown: page reloads, URL
   gains `?level=Broad|Fine`, Slept On ranking **and** the Diagnostics table
   (`feature_stats`) change between levels. Active `<option>` persists after reload.
3. **Toggle Include types** on: page reloads with `?include_types=true`, checkbox
   stays checked, type/subtype rows appear in Diagnostics and rankings shift;
   toggle off → param drops, default behavior returns.
4. **Tooltip ↔ diagnostics parity** (the core AC): at each of the three levels,
   hover a Slept On card and confirm every tooltip row's feature + weight matches a
   row in the Diagnostics table at that level, and that **no** tooltip row names a
   leaf tag absent from the card's current-level feature set. Verify with types on
   and off.
5. **Composition**: pick a real Theme tag **and** Level=Fine — the recommended set
   is tag-scoped and scored at fine granularity; both params coexist in the URL.
6. **No desync with Diagnostics mutes**: the client-only "Ignore types/subtypes"
   mutes in the Diagnostics tab still work and are visibly distinct from the
   server-recompute "Include card types & subtypes" control in `#controls`.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Checkbox toggle not caught by the existing `select[data-param]` handler (it reads `.value`, not `.checked`) → toggle does nothing | Task 4 adds a dedicated checkbox handler reading `.checked` and writing the literal `"true"` the route's strict-boolean parse expects. |
| User confuses the server "Include types" control with the Diagnostics display mutes | Task 2 tooltip + Task 3 scope-note explicitly call out the distinction; the two controls live in different tabs. |
| Level numbers leaking into the UI (PRD forbids) | Task 1 emits names only (`Broad`/`Balanced`/`Fine`); the name→depth map stays in `analysis.LEVEL_DEPTHS`, never in the template. |
| Tooltip drift from server scores | None introduced — JS already consumes server `data-features` verbatim against level-correct `WEIGHTS`; Task 5 only verifies + documents the invariant (no logic change). |
| `?include_types` accepting odd truthy values | Already handled by the route's strict `== "true"` parse (#41); the checkbox only ever emits `true` or removes the param. |
| Default render drifts | No params → route defaults Balanced + types-off (#41), and the selector/checkbox merely reflect `selected_level`/`include_types`; default page is unchanged. |

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] Named Level selector (**Broad / Balanced / Fine**, default Balanced, names
      only — no numbers) rendered in `#controls` beside the tag/budget/bracket
      selectors
- [ ] "Include card types & subtypes" toggle present (default off), visibly
      distinct from the Diagnostics display mutes
- [ ] Changing either control submits and triggers the server recompute
      (`?level` / `?include_types`), composing with the existing scope selectors
- [ ] Diagnostics table (`feature_stats`) reflects the chosen level/type settings
- [ ] Hover tooltip scores only from each card's server-emitted (level-capped)
      `features`; no independent leaf-tag expansion in JS; no leaf-tag rows for tags
      the card no longer scores on at the current level
- [ ] `flake8 .` clean; `python -m py_compile ...` clean
- [ ] Manual smoke test confirms tooltip contributions match the diagnostics table
      across all three levels (and both toggle states)
- [ ] GitHub Issue #42 criteria satisfied
