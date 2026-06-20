# Plan: Commander header (image + name) at top of the commander page

## Summary
The commander page currently opens with only a bare `<h1>{{ commander.name }}</h1>`
(`templates/commander.html:4`) — no card art identifying which commander you're looking
at. The `commander` context object already carries `name` and `image_uri` (from
`edhrec.get_commander_info`, passed at `app.py:85-92`), so this is a **template + CSS**
change with **no Python/route change**: replace the bare heading with a styled header
block showing the commander's art beside its name. The header markup iterates a list
that defaults to `[commander]`, so the partner-pairing work (#21) can render two
commanders by passing a 2-item `commanders` list with zero further header changes.

## User Story
As a Brewer, I want the searched commander displayed at the top of the page, so that I
always know which commander the recommendations are for.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW |
| GitHub Issue | #18 |
| Systems Affected | `templates/commander.html`, `static/css/style.css` |
| Dependencies | None. Forward-compatible with #21 (partner pairings). |

---

## Spike Findings (verified 2026-06-20)

- `app.py:85-92` renders `commander.html` with `commander=info`, where `info` =
  `{"name", "color_identity", "image_uri"}` (`services/edhrec.py:27-31`). The image is
  `image_uris[0].normal` — a full card image. **No new fetch needed** (satisfies the
  AC "no new per-request HTTP").
- Current header: `templates/commander.html:4` `<h1>{{ commander.name }}</h1>` and
  `:5` a `.copy-hint` tip line.
- `commander.name` is **also** used at `templates/commander.html:2` (page `<title>`)
  and `:83` (diagnostics copy: "{{ commander.name }}'s decks"). Keep `commander` in the
  context untouched so these keep working — only the on-page heading changes.
- Styling reference: dark palette `#1a1a2e` bg / `#e94560` accent (`style.css:4-8,34`);
  cards use `1px solid #0f3460` + `border-radius: 8px` (`style.css:330-342`). `h1` is
  already accent-colored (`style.css:34`). No image element exists for the commander yet.
- `image_uri` can rarely be empty; guard the `<img>` so an empty string doesn't render a
  broken image.

---

## Patterns to Follow

### Existing card image styling (match the look)
```css
/* SOURCE: static/css/style.css:330-342 */
.card-item { border: 1px solid #0f3460; border-radius: 8px; overflow: hidden; }
.card-item img { width: 100%; display: block; }
```

### Existing heading style (reused inside the header)
```css
/* SOURCE: static/css/style.css:34 */
h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #e94560; }
```

### Lazy image attribute used elsewhere
```html
<!-- SOURCE: templates/commander.html:36 -->
<img src="{{ card.image_uri }}" alt="{{ card.name }}" loading="lazy">
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `templates/commander.html` | UPDATE | Replace bare `<h1>` with a list-driven commander header (image + name). |
| `static/css/style.css` | UPDATE | Add `.commander-header` / `.commander-id` / `.commander-art` styles matching the palette. |

No files are created. No Python change.

---

## Tasks

Execute in order.

### Task 1: Replace the bare heading with a list-driven header block
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: Replace line 4 (`<h1>{{ commander.name }}</h1>`) with a header that
  iterates a commanders list defaulting to the single `commander` (keep the `.copy-hint`
  line 5 directly below it):
  ```jinja
  {% set header_commanders = commanders if (commanders is defined and commanders) else [commander] %}
  <header class="commander-header">
    {% for c in header_commanders %}
    <div class="commander-id">
      {% if c.image_uri %}<img class="commander-art" src="{{ c.image_uri }}" alt="{{ c.name }}" loading="lazy">{% endif %}
      <h1>{{ c.name }}</h1>
    </div>
    {% endfor %}
  </header>
  ```
  Do **not** change `templates/commander.html:2` (title) or `:83` (diagnostics) — they
  keep using the existing `commander` object. The `commanders` variable is intentionally
  not passed yet; the `is defined` guard makes the template safe today and ready for #21.
- **Mirror**: `templates/commander.html:36` (lazy `<img>`), heading from `:4`.
- **Validate**: page renders (Task 3 smoke test); no `UndefinedError` for `commanders`.

### Task 2: Add commander-header styles
- **File**: `static/css/style.css`
- **Action**: UPDATE
- **Implement**: Add a small style block (place it near the top of the commander-page
  styles, e.g. just after the `h1`/`p` rules around line 35) matching the existing
  palette and card treatment:
  ```css
  /* ── Commander header ── */
  .commander-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }
  .commander-id { display: flex; align-items: center; gap: 0.75rem; }
  .commander-art {
    width: 110px;
    border: 1px solid #0f3460;
    border-radius: 8px;
    display: block;
  }
  .commander-header h1 { margin-bottom: 0; }
  ```
  Keep the global `h1` rule intact; `.commander-header h1` only drops its bottom margin
  so it aligns vertically centered with the art. Two `.commander-id` blocks (a pairing)
  will sit side by side and wrap on narrow widths via `flex-wrap`.
- **Mirror**: `static/css/style.css:330-342` (card border/radius), `:34` (h1 accent).
- **Validate**: `flake8 .` (unaffected — no .py changed); visual check in Task 3.

### Task 3: Manual smoke test
- **File**: n/a
- **Action**: verify
- **Implement**:
  1. `python app.py`, open `/commander/atraxa-praetors-voice`.
  2. Confirm the top of the page shows Atraxa's card art next to the name "Atraxa,
     Praetors' Voice", styled consistently with the rest of the page.
  3. Confirm the page `<title>` and the Diagnostics "…'s decks" copy still show the
     commander name (i.e., `commander` context still intact).
  4. Confirm tabs, filters, and copy-to-clipboard still work (no markup regressions).
- **Validate**: visual; header renders with image + name; no console/template errors.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
python app.py   # load /commander/atraxa-praetors-voice and eyeball the header
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `commanders` is referenced but never passed → Jinja `UndefinedError` | Guarded with `commanders is defined and commanders`, falling back to `[commander]`. Safe today; #21 just passes the list. |
| Empty `image_uri` renders a broken image | `{% if c.image_uri %}` wraps the `<img>`; name still shows. |
| Full card art is large/portrait and dominates the header | Fixed `width: 110px` keeps it a thumbnail; `flex-wrap` handles small screens. |
| Removing the old `<h1>` breaks other `commander.name` usages | Those usages (`:2`, `:83`) read the `commander` context object, which is unchanged; only the on-page heading moved into `.commander-header`. |

---

## Forward-Compatibility Note (for #21)
When partner pairings land, the route will pass `commanders=[info1, info2]` (and decide
what `commander`/title shows for a pairing). This header already loops that list — no
header markup or CSS change required, only the new context variable.

---

## Acceptance Criteria

- [ ] Commander page shows a header with the commander's image and name at the top.
- [ ] Header markup accommodates two commanders (list-driven; renders both when a
      `commanders` list is supplied) — single-commander path works now.
- [ ] Header data comes from the existing `commander` lookup (no new per-request HTTP).
- [ ] `flake8 .` clean; `py_compile` clean (no Python changed).
- [ ] Smoke test: `/commander/atraxa-praetors-voice` shows Atraxa's image + name.
- [ ] Follows CLAUDE.md layering (display-only template change; no logic in templates).
- [ ] GitHub Issue #18 criteria satisfied.
```
