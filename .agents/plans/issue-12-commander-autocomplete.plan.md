# Plan: Offline Commander-Name Autocomplete on the Search Bar

## Summary
Add as-you-type commander suggestions to the landing-page search box, drawn from the local
Scryfall bulk store (no per-keystroke network). The list is the set of legal commanders —
legendary creatures plus cards whose oracle text says "can be your commander" — built once from
the bulk store and served as a small JSON asset. The input uses a native HTML5 `<datalist>`
populated by a one-time `fetch`, which gives filtering, a dropdown, and full keyboard navigation
for free, works offline, and ships cleanly in the static export. Independent of issues #10/#11.

## User Story
As a deckbuilder, I want commander-name suggestions as I type in the search bar, so that I can
find the exact commander quickly without misspelling it or guessing the slug.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | MEDIUM |
| GitHub Issue | #12 |
| Systems Affected | `services/bulk.py`, `app.py` (new route), `templates/index.html`, new `static/js/autocomplete.js`, `export.py` |

---

## Design Decision (please review)

**Use a native `<datalist>` populated by a single `fetch`, not a hand-rolled JS dropdown.**
The issue's technical notes sketch a custom debounced dropdown capped to ~10 results. A
`<datalist>` satisfies every acceptance criterion with far less code and risk:
- dropdown of matching names ✔ (browser filters as you type)
- commanders only ✔ (we control the option list)
- offline / no per-keystroke network ✔ (list fetched once, then local)
- selecting navigates ✔ (fills the input; existing form submit → `/commander/<slug>`)
- keyboard navigation (arrows + Enter) ✔ (native)
- works in the static export ✔ (it's plain HTML + a local JSON file)

Trade-off: less visual control and browser-dependent match style (Chrome substring, Firefox
prefix). For a personal tool this is the right call; a custom dropdown remains a follow-up if
styling/`~10`-cap is wanted later. **The plan proceeds with `<datalist>`.**

---

## Patterns to Follow

### Bulk store trimmed record + helpers
SOURCE: `services/bulk.py` `_trim` (~`:135`) — builds the per-card record kept in memory; today it
keeps `name, oracle_id, type_line, color_identity, price_usd, rarity, image_uri, edhrec_rank,
commander_legal, layout` (no `oracle_text`). SOURCE: `services/bulk.py` `color_identity_pool` /
`card_record` — existing public helpers that call `ensure_loaded()` and read `_cards`/`_by_name`.
New `commander_names()` follows the same shape (calls `ensure_loaded()`, reads `_cards`, memoized).

### Front-face naming (for DFC commanders)
SOURCE: `services/bulk.py` `_build_card_index` — already splits `"A // B"` and indexes the front
face `"A"`. Commander suggestions must use the front-face name so `edhrec.slugify` produces a slug
EDHRec recognizes (e.g. "Esika, God of the Tree", not the full "… // The Prismatic Bridge").

### Search route + slugify
SOURCE: `app.py:16-22` index route → `redirect(url_for("commander", slug=edhrec.slugify(name)))`.
Autocomplete only fills the input; submission stays exactly as-is.

### Client JS convention
SOURCE: `static/js/filters.js` — vanilla JS, `DOMContentLoaded`, no framework, included via the
`{% block scripts %}` in `base.html`. New `autocomplete.js` follows this.

### Static export
SOURCE: `export.py` — `main()` copies `static/` → `docs/static/` and writes a hand-built
`docs/index.html` (`export_index`); `_fix_paths` rewrites `/static/` → `static/`. The commander
JSON must be written into `docs/` so the relative `fetch("commanders.json")` resolves offline.

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/bulk.py` | UPDATE | Add `can_be_commander` to `_trim`; add memoized `commander_names()` returning sorted unique front-face commander names |
| `app.py` | UPDATE | Add a `GET /commanders.json` route returning the commander list (lazily warms the bulk store) |
| `templates/index.html` | UPDATE | Add `list="commander-list"` to the input + an empty `<datalist>`; include `autocomplete.js` via the scripts block |
| `static/js/autocomplete.js` | CREATE | Fetch `commanders.json` once and inject `<option>`s into the datalist |
| `export.py` | UPDATE | Write `docs/commanders.json` (from `bulk.commander_names()`) so the static build has the list |

No change to `services/analysis.py` or `services/scryfall.py`.

---

## Design Notes / Decisions

- **Commander detection** (in `_trim`): compute a boolean once and store it (don't retain the full
  oracle text). Rule:
  `legendary_creature = ("Legendary" in type_line and "Creature" in type_line)`;
  `can_be_commander = legendary_creature or ("can be your commander" in oracle_text.lower())`,
  where `oracle_text` is `raw.get("oracle_text","")` plus any `card_faces[*].oracle_text`. This is
  the standard `is:commander` heuristic (covers legendary creatures, the "can be your commander"
  planeswalkers/Backgrounds). Exclude excluded-layout records (already skipped at index build).
- **`commander_names()`**: iterate `_cards`, keep `rec["can_be_commander"]`, map each `name` to its
  front face (`name.split(" // ", 1)[0]`), dedupe, sort case-insensitively. Memoize in a module
  global so it's built once per process.
- **Delivery path**: live app serves `/commanders.json`; the JS does a single relative
  `fetch("commanders.json")`. On the index page `"/"` this resolves to the route; in the static
  export (`docs/index.html`) it resolves to `docs/commanders.json`. One asset, both contexts.
- **Cold-start**: the first hit to `/commanders.json` on a cold server triggers `warm_up()`
  (~30s bulk build). The landing page renders immediately and stays usable (user can type/submit);
  suggestions populate when the fetch resolves. Acceptable for a local tool — note, don't block render.
- **Static `export_index` scope**: the existing static index is a hand-built link list of only the
  *pre-generated* commanders; full-catalog search there isn't meaningful (those pages don't exist).
  This issue makes the autocomplete **mechanism** export-safe (writes `docs/commanders.json`, JS is
  static) and wires it into the live `templates/index.html`. Converting the static index into a
  datalist search over exported commanders is noted as a small follow-up, not required here.

---

## Tasks

### Task 1: Flag commanders in the bulk store
- **File**: `services/bulk.py`
- **Action**: UPDATE
- **Implement**: In `_trim`, read oracle text from `card.get("oracle_text","")` plus any
  `card.get("card_faces")` face texts, and add `"can_be_commander": <bool>` per the rule above
  (legendary creature OR "can be your commander" in the lowercased text). Keep the record otherwise
  unchanged (do not store the raw text).
- **Mirror**: existing `_trim` field assembly and `_image_uri`'s card_faces handling.
- **Validate**: `.venv/Scripts/python.exe -m py_compile services/bulk.py`

### Task 2: Add the `commander_names()` helper
- **File**: `services/bulk.py`
- **Action**: UPDATE
- **Implement**: Add a module-global memo (e.g. `_commander_names = None`) and
  `def commander_names() -> list[str]:` that calls `ensure_loaded()`, builds (once) a sorted, deduped
  list of front-face names from `_cards` where `rec["can_be_commander"]`, caches it, and returns it.
  Reset the memo in `ensure_loaded()` if/when indices rebuild (mirror how `_loaded` gates rebuilds).
- **Mirror**: `color_identity_pool` (calls `ensure_loaded`, reads `_cards`).
- **Validate**: `py_compile` + a quick REPL check that the list is non-empty and contains a known
  commander (e.g. "Atraxa, Praetors' Voice").

### Task 3: Serve the list from a route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**: Import `jsonify` (and `bulk` from `services`). Add
  `@app.route("/commanders.json")` → `scryfall.warm_up()` then
  `return jsonify(bulk.commander_names())`. Keep it thin (route-only, per CLAUDE.md layering).
- **Mirror**: existing route style in `app.py`.
- **Validate**: `.venv/Scripts/python.exe -m py_compile app.py`

### Task 4: Wire the datalist into the landing page
- **File**: `templates/index.html`
- **Action**: UPDATE
- **Implement**: Add `list="commander-list"` and `autocomplete="off"` to the `<input>`; add an empty
  `<datalist id="commander-list"></datalist>`; add a `{% block scripts %}` including
  `static/js/autocomplete.js`.
- **Mirror**: `commander.html` scripts block / `base.html`'s `{% block scripts %}`.
- **Validate**: page renders 200 (Task 7).

### Task 5: Populate the datalist client-side
- **File**: `static/js/autocomplete.js`
- **Action**: CREATE
- **Implement**: On `DOMContentLoaded`, guard for `#commander-list`; `fetch("commanders.json")`,
  on success build a `DocumentFragment` of `<option value="name">` and append to the datalist in one
  insert. Fail silently on fetch error (search still works without suggestions).
- **Mirror**: `static/js/filters.js` structure (DOMContentLoaded + element guard).
- **Validate**: `node --check static/js/autocomplete.js`

### Task 6: Ship the list with the static export
- **File**: `export.py`
- **Action**: UPDATE
- **Implement**: In `main()` (after static copy), write `DOCS_DIR / "commanders.json"` with
  `json.dumps(bulk.commander_names())`. Import what's needed (`json`, `services.bulk`).
- **Mirror**: existing file-writing in `export_index`.
- **Validate**: `.venv/Scripts/python.exe -m py_compile export.py`

### Task 7: Verify end-to-end
- **File**: n/a
- **Action**: VERIFY
- **Implement**: `flake8 .`; run the app; on `/`, type "atra" and confirm an "Atraxa…" suggestion
  appears, arrow-select + Enter navigates to the commander page; confirm only ONE network request
  for `commanders.json` (no per-keystroke calls) via devtools; confirm non-commander cards are absent
  from suggestions. Run `python export.py "Atraxa, Praetors' Voice"`, confirm `docs/commanders.json`
  exists and the JS loads it relative when `docs/index.html` is opened with no server.
- **Validate**: see Validation Sequence.

---

## Validation Sequence
```bash
.venv/Scripts/python.exe -m flake8 .
.venv/Scripts/python.exe -m py_compile app.py services/bulk.py export.py
node --check static/js/autocomplete.js
# manual: run app.py, type in the search box; then run export.py and open docs/index.html
```

---

## Risks & Mitigations
| Risk | Mitigation |
|------|-----------|
| Cold-server first `/commanders.json` blocks ~30s on bulk build | Fetch is async/non-blocking; page renders and stays usable; suggestions appear when ready. Don't await it on render |
| DFC commander suggestion produces a bad EDHRec slug | Suggest the **front-face** name (`split(" // ")[0]`), matching how EDHRec slugs DFC commanders |
| Datalist match style differs by browser (substring vs prefix) | Acceptable for v1; documented. Custom dropdown is the follow-up if needed |
| `oracle_text` adds memory if retained | Store only the `can_be_commander` boolean in `_trim`; discard the text |
| `commanders.json` path resolves differently live vs export | Use a relative `fetch("commanders.json")`; serve via route live and write `docs/commanders.json` in export |

---

## Acceptance Criteria
- [ ] All tasks completed
- [ ] `flake8 .` passes; `py_compile` clean; `node --check` clean
- [ ] Typing in the search box shows matching commander suggestions
- [ ] Suggestions are commanders only (legendary creatures + "can be your commander")
- [ ] List loads once (no per-keystroke network call)
- [ ] Selecting a suggestion navigates to the commander page
- [ ] Keyboard navigation works (arrows + Enter)
- [ ] `docs/commanders.json` is written by `export.py`; the JS loads it relative with no server
- [ ] Follows existing patterns; `services/bulk.py` stays I/O-isolated, route stays thin
- [ ] GitHub Issue #12 criteria satisfied
