# Plan: Split diagnostics toggle into independent ignore-types / ignore-subtypes checkboxes

## Summary
The Diagnostics tab has one bulk checkbox, "Ignore types & subtypes"
(`#mute-types-subs`), that mutes every `type:*` and `sub:*` feature together. This
change replaces it with two independent checkboxes — "Ignore types" and "Ignore
subtypes" — each muting only its own feature kind, in any combination. It's a
display/diagnostics-only change wired through the existing live re-score machinery
(`setMuted` / `rescore`); the scoring math in `services/analysis.py` is untouched.
Touches the template, `filters.js`, and the CSS that styled the old control.

## User Story
As a Brewer, I want to ignore card types and subtypes independently in the diagnostics
tab, so that I can isolate how oracle tags (or types, or subtypes) alone drive the score.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW |
| GitHub Issue | #20 |
| Systems Affected | `templates/commander.html`, `static/js/filters.js`, `static/css/style.css` |
| Dependencies | None. Independent of #15–#19, #21, #22 (only touches the diagnostics control). |

---

## Spike Findings (verified 2026-06-20)

- **Markup**: single bulk control at `templates/commander.html:89-91`:
  ```html
  <label id="mute-types-subs-control">
    <input type="checkbox" id="mute-types-subs"> Ignore types &amp; subtypes
  </label>
  ```
- **JS**: `static/js/filters.js:93` grabs `muteTypesSubs`; handler `:107-120` mutes
  every `type:`/`sub:` feature, syncing the per-row checkboxes, then `rescore()`.
  Reusable helpers already exist: `setMuted(feature, isMuted, row)` (`:96-99`),
  `rescore()` (`:101-105`), and `featureToggles` (`:94`, the per-row checkboxes).
- **CSS**: two rules reference the old ids — `#mute-types-subs-control` (`style.css:283-289`,
  label layout) and `#mute-types-subs` (`:291-292`, checkbox accent/size). Both must be
  updated or they'll dangle.
- Feature kinds are namespaced `type:` / `sub:` / `otag:` (`services/analysis.py:37-60
  card_features`); each diagnostics row carries `data-feature` on its toggle
  (`templates/commander.html:101-102`). No Python change needed.

---

## Patterns to Follow

### Existing bulk-mute handler (generalize this)
```javascript
// SOURCE: static/js/filters.js:107-120
if (muteTypesSubs) {
  muteTypesSubs.addEventListener('change', () => {
    const mute = muteTypesSubs.checked;
    featureToggles.forEach(cb => {
      const f = cb.dataset.feature;
      if (f.startsWith('type:') || f.startsWith('sub:')) {
        cb.checked = !mute;
        setMuted(f, mute, cb.closest('tr'));
      }
    });
    rescore();
  });
}
```

### Per-row toggle + shared helpers (reuse unchanged)
```javascript
// SOURCE: static/js/filters.js:96-105
function setMuted(feature, isMuted, row) { ... }
function rescore() { recomputeScores(); reorderSleptOn(); applyFilters(); }
```

### Control markup + CSS to mirror
```html
<!-- SOURCE: templates/commander.html:89-91 -->
```
```css
/* SOURCE: static/css/style.css:283-292 */
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `templates/commander.html` | UPDATE | Replace the one bulk checkbox with two independent ones. |
| `static/js/filters.js` | UPDATE | Bind each checkbox to mute only its kind via a small reusable helper. |
| `static/css/style.css` | UPDATE | Re-point the control/checkbox styles to the new elements. |

No files are created. No Python change.

---

## Tasks

Execute in order.

### Task 1: Replace the single control with two checkboxes
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: Replace lines 89-91 with two independent labelled checkboxes in a
  shared container:
  ```html
  <div class="mute-kind-controls">
    <label class="mute-kind-control"><input type="checkbox" id="mute-types" class="mute-kind"> Ignore types</label>
    <label class="mute-kind-control"><input type="checkbox" id="mute-subs" class="mute-kind"> Ignore subtypes</label>
  </div>
  ```
  Keep the surrounding Diagnostics markup (intro `<p>`, the `diag-table`) unchanged.
- **Mirror**: `templates/commander.html:89-91`.
- **Validate**: page renders (Task 4).

### Task 2: Bind each checkbox to its own feature kind
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**:
  1. Remove the `const muteTypesSubs = document.getElementById('mute-types-subs');`
     line (`:93`) and the whole `if (muteTypesSubs) { ... }` handler (`:107-120`).
  2. Add a reusable helper + two bindings (place where the old block was, after
     `featureToggles` is defined at `:94` and after `setMuted`/`rescore` are defined):
     ```javascript
     // Bulk: mute/unmute every feature of one kind (type:* or sub:*), syncing the
     // per-row checkboxes, then re-score. Each kind toggles independently.
     function bindKindMute(checkboxId, prefix) {
       const box = document.getElementById(checkboxId);
       if (!box) return;
       box.addEventListener('change', () => {
         const mute = box.checked;
         featureToggles.forEach(cb => {
           if (cb.dataset.feature.startsWith(prefix)) {
             cb.checked = !mute;
             setMuted(cb.dataset.feature, mute, cb.closest('tr'));
           }
         });
         rescore();
       });
     }
     bindKindMute('mute-types', 'type:');
     bindKindMute('mute-subs', 'sub:');
     ```
  Leave the per-row `featureToggles` listeners (`:123-128`) and everything else intact.
- **Mirror**: `static/js/filters.js:107-120` (generalized), `:96-105` (helpers reused).
- **Validate**: no `mute-types-subs` reference remains:
  `grep -n "mute-types-subs" static/js/filters.js` returns nothing.

### Task 3: Re-point the CSS to the new elements
- **File**: `static/css/style.css`
- **Action**: UPDATE
- **Implement**:
  1. Replace the `#mute-types-subs-control` selector (`:283`) with `.mute-kind-control`
     (keep the same declarations), and add a flex container rule so the two sit inline:
     ```css
     /* Bulk per-kind "Ignore types" / "Ignore subtypes" controls above the table. */
     .mute-kind-controls { display: flex; gap: 1rem; margin: 0.5rem 0; flex-wrap: wrap; }
     .mute-kind-control {
       font-size: 0.85rem;
       color: #aac4e8;
       cursor: pointer;
     }
     ```
     (Drop the old `display: inline-block; margin: 0.5rem 0;` from the label since the
     container now handles layout.)
  2. Update the checkbox-styling rule (`:291-292`) so the accent/size applies to the new
     boxes — change `#mute-types-subs` to `.mute-kind`:
     ```css
     .diag-table input[type="checkbox"],
     .mute-kind { accent-color: #e94560; width: 16px; height: 16px; cursor: pointer; }
     ```
- **Mirror**: `static/css/style.css:282-292`.
- **Validate**: `grep -n "mute-types-subs" static/css/style.css` returns nothing.

### Task 4: Manual smoke test
- **File**: n/a
- **Action**: verify
- **Implement**:
  1. `python app.py`, open a commander page, go to the **Diagnostics** tab.
  2. Check **Ignore types** only → all `type:*` rows dim/strike-through and are muted;
     `sub:*` and `otag:*` rows stay active. Slept On re-scores/re-ranks accordingly.
  3. Check **Ignore subtypes** only (types unchecked) → only `sub:*` rows mute.
  4. Check **both** → both kinds mute, `otag:*` unaffected; uncheck both → all restored.
  5. Confirm per-row toggles still work alongside the bulk checkboxes.
- **Validate**: visual; each checkbox affects only its kind; scores update live.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
grep -rn "mute-types-subs" templates/ static/   # expect: no matches
python app.py   # exercise Diagnostics toggles
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Dangling `#mute-types-subs` CSS/JS references after rename | Tasks 2 & 3 explicitly replace both; validation greps for leftovers. |
| Bulk checkbox desyncs from per-row toggles | Reuses the existing `setMuted` + per-row `cb.checked = !mute` sync, exactly as the old handler did. |
| Accidentally touching scoring math | Pure display/diagnostics change; `services/analysis.py` untouched (out of scope per issue). |

---

## Acceptance Criteria

- [ ] The single `#mute-types-subs` checkbox is replaced by independent
      `#mute-types` ("Ignore types") and `#mute-subs` ("Ignore subtypes").
- [ ] Each checkbox toggles only its own kind (`type:` vs `sub:`).
- [ ] Any combination works (both / either / neither).
- [ ] No dangling references to the old id in templates, JS, or CSS.
- [ ] `flake8 .` clean; `py_compile` clean (no Python changed).
- [ ] Smoke test: "Ignore types" alone leaves subtype-driven weights visible.
- [ ] Follows CLAUDE.md (display-only; logic stays in JS, math stays in analysis.py).
- [ ] GitHub Issue #20 criteria satisfied.
```
