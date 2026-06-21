# Plan: Partner commander pairings (partner / background / friends forever)

## Summary
Support two-commander pairings end to end. The key realization from the spike: a
pairing is just a **combined EDHRec slug** on the same endpoint #15 already uses —
`json.edhrec.com/pages/commanders/thrasios-triton-hero-tymna-the-weaver.json` returns
a combined `card` with `names: [n1, n2]`, `image_uris: [{…},{…}]`, and a **union**
`color_identity`, plus the usual combined cardlists. So the whole scoring/Slept On
pipeline (#15) works **unchanged** if we route a pairing through `/commander/<combined-slug>`.
The new work is narrow: (1) classify partner eligibility + legal pairings from the
**Scryfall bulk store** (EDHRec's single-commander JSON doesn't list partners); (2) a
`/partners` lookup route feeding a restricted second autocomplete on the landing page;
(3) build the pairing slug on submit and redirect; (4) split the combined card into two
header infos for #18's header and exclude both names from Slept On.

## User Story
As a Brewer, I want to build a partner pairing, so that recommendations reflect both
commanders.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | HIGH |
| GitHub Issue | #21 |
| Systems Affected | `services/bulk.py`, `services/edhrec.py`, `app.py`, `templates/index.html`, `static/js/autocomplete.js` |
| **Blocked by** | **#15** (`get_commander_data`, `cards_from_data`, `inclusion_index_from_data`, `commander_info_from_data`) and **#18** (header renders a `commanders` list). Coexists with #19 (scope params also work on a pairing slug). |

---

## Spike Findings (verified live, 2026-06-20)

- **Combined page**: `GET /pages/commanders/<slugA>-<slugB>.json` → 200 with
  `container.json_dict.card` carrying:
  - `names: ["Thrasios, Triton Hero", "Tymna the Weaver"]`
  - `image_uris: [{"normal","art_crop"}, {"normal","art_crop"}]` (one per commander)
  - `color_identity: ["G","W","U","B"]` (already the **union**)
  - flags `is_partner`, `legal_partner`, `legal_commander`.
  The non-canonical ordering (`tymna…-thrasios…`) returned 200 but **without** a usable
  `container` → **must try both orderings** and keep the one with a valid container.
- **Single-commander JSON does NOT enumerate legal partners** (Tymna's page has no
  partner panel; only `card.legal_partner: true`). → derive legal pairings from
  **Scryfall**.
- **Scryfall signals** (from bulk `default_cards`, already downloaded):
  - `keywords` contains `"Partner"` → generic partner (also true for "Partner with X"
    cards — and per the rules a Partner-with card may pair with *any* Partner card, so
    we treat them all as one pool; the named partner is a non-binding bonus).
  - `keywords` contains `"Friends forever"` → friends-forever pool.
  - `keywords` contains `"Choose a background"` → pairs with any **Background**.
  - `type_line` contains `"Background"` → a Background (pairs with any "Choose a
    Background" commander).
- The existing bulk `_trim` (`services/bulk.py:151-165`) does **not** retain `keywords`
  or `oracle_text`; `_can_be_commander` (`:137-148`) already reads face oracle text, so
  partner classification can be computed in the same place during index build.

---

## Design

### Partner classification (computed in bulk during `_trim`)
Add `partner_kind` ∈ `{"", "partner", "friends_forever", "choose_background", "background"}`
to each trimmed record:
- `"partner"` if any keyword starts with "partner" (covers "Partner" and "Partner with").
- `"friends_forever"` if a keyword/oracle text has "friends forever".
- `"choose_background"` if a keyword/oracle text has "choose a background".
- `"background"` if `type_line` contains "Background".
- else `""`.
(Priority: friends_forever / choose_background / partner are mutually exclusive in
practice; check background by type separately.)

### Legal partners (pure bulk lookup)
`legal_partners_for(name)` maps the picked card's `partner_kind` to a candidate pool:
- `partner` → all other commander records with `partner_kind == "partner"`.
- `friends_forever` → all other `friends_forever`.
- `choose_background` → all `background` records.
- `background` → all `choose_background` records.
- else → `[]`.
Sorted, deduped names. Built from module-level indices (memoized like
`_commander_names`).

### Routing a pairing
- New `GET /partners?name=<n>` → `{"eligible": bool, "kind": str, "partners": [names]}`.
- Index `POST`: if a `partner` field is present, `edhrec.resolve_pairing_slug(name, partner)`
  picks the EDHRec-valid ordering; redirect to `/commander/<combined-slug>`. Else single
  commander as today.
- `/commander/<slug>` is unchanged in spirit — a pairing is just a slug whose EDHRec
  `card.names` has two entries. The route passes a 2-item `commanders` list (header) and
  excludes both names from Slept On. Union color identity flows through `info.color_identity`.

---

## Patterns to Follow

### Bulk classification during trim (extend this)
```python
# SOURCE: services/bulk.py:137-165 (_can_be_commander reads face oracle text; _trim shapes the record)
def _can_be_commander(card):
    ...
    texts = [card.get("oracle_text", "")]
    texts += [face.get("oracle_text", "") for face in card.get("card_faces") or []]
    ...
def _trim(card):
    return { "name": ..., "can_be_commander": _can_be_commander(card), ... }
```

### Memoized derived index (mirror exactly)
```python
# SOURCE: services/bulk.py:324-338 (commander_names — memoized, rebuilt on reload)
def commander_names():
    global _commander_names
    ensure_loaded()
    if _commander_names is None:
        _commander_names = sorted({...}, key=str.casefold)
    return _commander_names
```

### JSON route + bulk warm-up (mirror exactly)
```python
# SOURCE: app.py:25-30 (/commanders.json)
@app.route("/commanders.json")
def commanders_json():
    scryfall.warm_up()
    return jsonify(bulk.commander_names())
```

### Index POST → redirect (extend)
```python
# SOURCE: app.py:16-22
name = request.form.get("commander", "").strip()
if name:
    return redirect(url_for("commander", slug=edhrec.slugify(name)))
```

### EDHRec fetch + commander info (extend for the 2-name card)
```python
# SOURCE: services/edhrec.py:16-34 (image_uris is always a list; single uses [0].normal)
image_uris = card.get("image_uris", [])
if image_uris: image_uri = image_uris[0].get("normal", "")
```

### Autocomplete structure to generalize
```javascript
// SOURCE: static/js/autocomplete.js:1-24 (single-input IIFE; fetch('commanders.json'); findMatches)
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/bulk.py` | UPDATE | `partner_kind` in `_trim`; `legal_partners_for` + `partner_eligibility` + indices. |
| `services/edhrec.py` | UPDATE | `commanders_from_data(data)`; `resolve_pairing_slug(a, b)`. |
| `app.py` | UPDATE | `/partners` route; index POST pairing handling; commander route passes `commanders` + excludes both names. |
| `templates/index.html` | UPDATE | Hidden second (partner) input + its suggestion list. |
| `static/js/autocomplete.js` | UPDATE | Generalize to two inputs; reveal restricted partner input when eligible. |

No new dependencies.

---

## Tasks

Execute in order.

### Task 1: Classify partner eligibility in the bulk store
- **File**: `services/bulk.py`
- **Action**: UPDATE
- **Implement**:
  1. Add `_partner_kind(card) -> str` near `_can_be_commander` (`:137`), reading
     `card.get("keywords") or []`, `type_line`, and face oracle texts (reuse the same
     face-collection idiom):
     ```python
     def _partner_kind(card):
         kws = [k.lower() for k in (card.get("keywords") or [])]
         type_line = card.get("type_line", "")
         texts = " ".join([card.get("oracle_text", "")] +
                          [f.get("oracle_text", "") for f in card.get("card_faces") or []]).lower()
         if any("friends forever" in k for k in kws) or "friends forever" in texts:
             return "friends_forever"
         if any("choose a background" in k for k in kws) or "choose a background" in texts:
             return "choose_background"
         if any(k.startswith("partner") for k in kws) or "\npartner" in ("\n"+texts):
             return "partner"
         if "Background" in type_line:
             return "background"
         return ""
     ```
  2. Add `"partner_kind": _partner_kind(card)` to the dict returned by `_trim` (`:152-165`).
  3. Add memoized indices (module-level, reset in `ensure_loaded` alongside
     `_commander_names`): build, on first use, name lists keyed by kind from `_cards`
     (filter `commander_legal` for partner/friends/choose_background; `background` from
     type regardless of `can_be_commander`).
  4. Add public lookups:
     ```python
     def partner_eligibility(name) -> dict:
         """{'eligible': bool, 'kind': str, 'partners': [name,...]} for a card."""
     def legal_partners_for(name) -> list[str]:
         """Sorted legal partner names per the card's partner_kind (see Design)."""
     ```
     Use front-face name lookup via `card_record(name)` (`:299-302`).
- **Mirror**: `services/bulk.py:137-165` (classification + trim), `:324-338` (memoized index).
- **Validate**: `flake8 services/bulk.py && python -m py_compile services/bulk.py`;
  quick REPL: `bulk.legal_partners_for("Tymna the Weaver")` is non-empty and contains
  "Thrasios, Triton Hero".

### Task 2: Pairing helpers in edhrec.py
- **File**: `services/edhrec.py`
- **Action**: UPDATE
- **Implement**:
  1. `commanders_from_data(data) -> list[dict]`: from `data["card"]`, return one
     `{"name","image_uri"}` per entry in `card["names"]` (fallback `[card["name"]]`),
     pulling `image_uris[i]["normal"]` when present. 1 entry for a single commander, 2
     for a pairing. Pure.
  2. `resolve_pairing_slug(name_a, name_b) -> str`: compute `sa, sb = slugify(a),
     slugify(b)`; for `combo in (f"{sa}-{sb}", f"{sb}-{sa}")` return the first whose
     `get_commander_data(combo)` is truthy (valid container); else fall back to
     `f"{sa}-{sb}"`. (Two cheap fetches at submit time; acceptable.)
- **Mirror**: `services/edhrec.py:12-34` (`slugify`, fetch shape).
- **Validate**: `flake8 services/edhrec.py && python -m py_compile services/edhrec.py`

### Task 3: Routes — `/partners`, pairing submit, pass `commanders`
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  1. Add a JSON route (mirror `/commanders.json`):
     ```python
     @app.route("/partners")
     def partners():
         scryfall.warm_up()
         name = request.args.get("name", "").strip()
         return jsonify(bulk.partner_eligibility(name))
     ```
  2. Extend the index `POST` (`:18-21`): read optional `partner`; if present,
     `slug = edhrec.resolve_pairing_slug(name, partner)`, else `edhrec.slugify(name)`;
     redirect to `commander`.
  3. In the commander route (post-#15), after `data = edhrec.get_commander_data(slug)`
     and `info = edhrec.commander_info_from_data(data)`, add
     `commanders = edhrec.commanders_from_data(data)` and pass `commanders=commanders`
     to `render_template` (feeds #18's header). Build the Slept On exclusion set from
     **every** name in `commanders` (plus `edhrec_cards`), not just `info["name"]`:
     ```python
     edhrec_names = {analysis.normalize_name(c["name"]) for c in edhrec_cards}
     for cm in commanders:
         edhrec_names.add(analysis.normalize_name(cm["name"]))
     ```
     Union color identity already comes from `info["color_identity"]` (the combined
     card) → color pool needs no change.
- **Mirror**: `app.py:25-30` (json route), `:16-22` (index), `:60-66` (exclusion set).
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 4: Landing-page second (partner) input
- **File**: `templates/index.html`
- **Action**: UPDATE
- **Implement**: Add, after the first `.autocomplete` block (`:7-14`), a second one that
  starts hidden and is revealed by JS when commander 1 is partner-eligible:
  ```html
  <div class="autocomplete" id="partner-wrap" hidden>
    <input type="text" name="partner" id="partner-input" placeholder="partner / background…"
           autocomplete="off" role="combobox" aria-autocomplete="list"
           aria-controls="partner-suggestions" aria-expanded="false">
    <ul id="partner-suggestions" class="autocomplete-list" role="listbox" hidden></ul>
  </div>
  ```
  Keep the single `<button>Analyze</button>` and POST target. `partner` is optional, so
  no `required`.
- **Mirror**: `templates/index.html:7-14`.
- **Validate**: page renders (Task 6).

### Task 5: Wire two autocompletes + eligibility reveal
- **File**: `static/js/autocomplete.js`
- **Action**: UPDATE
- **Implement**: Refactor the single-input IIFE into a reusable
  `setupAutocomplete(input, listEl, getNames)` where `getNames()` returns the current
  candidate array (preserve the existing ranking in `findMatches` `:26-34`, Tab-complete,
  keyboard nav, and the `hint` behavior for the primary input only). Then:
  1. Primary input: `setupAutocomplete(commanderInput, commanderList, () => names)` with
     `names` fetched from `commanders.json` as today (`:15-24`).
  2. On the primary input committing a value (selection/blur/Enter on a real name),
     `fetch('/partners?name=' + encodeURIComponent(value))`; if `data.eligible`, unhide
     `#partner-wrap`, set a module var `partnerNames = data.partners`, and initialize
     `setupAutocomplete(partnerInput, partnerList, () => partnerNames)` once. If not
     eligible, hide `#partner-wrap` and clear the partner input (so changing commander 1
     re-evaluates).
  3. Guard: keep the early `if (!input || !list) return;` for pages without the search box.
- **Mirror**: `static/js/autocomplete.js:1-24` (fetch + guard), `:26-34` (ranking).
- **Validate**: page interaction (Task 6).

### Task 6: Manual smoke test
- **File**: n/a
- **Action**: verify
- **Implement**:
  1. `python app.py`, landing page. Type "Tymna the Weaver" → second input appears,
     restricted to legal partners; pick "Thrasios, Triton Hero"; Analyze.
  2. Redirects to `/commander/thrasios-triton-hero-tymna-the-weaver`; **header shows both
     commanders** (image + name, via #18); Slept On + EDHRec render from the combined
     WUBG data with a coherent list.
  3. Type a non-partner commander (e.g. "Atraxa, Praetors' Voice") → no second input;
     single-commander flow unchanged.
  4. Type a "Choose a Background" commander (e.g. "Wilson, Refined Grizzly") → second
     input lists Backgrounds; pick one; pairing page renders.
  5. Confirm neither commander appears in its own Slept On list; `flake8 .` clean.
- **Validate**: visual + flake8; pairing renders both commanders and a union-CI Slept On.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py services/bulk.py
python app.py   # exercise the pairing flow from the landing page
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Implemented before #15/#18 | Marked **Blocked by**; verify `get_commander_data`/`commander_info_from_data` and the header `commanders` loop exist first. |
| EDHRec pairing slug ordering isn't always alphabetical (esp. backgrounds) | `resolve_pairing_slug` tries both orderings and keeps the one with a valid container; falls back gracefully. |
| Scryfall keyword strings vary ("Choose a background" casing, "Partner with") | Classification lowercases keywords + oracle text and matches substrings; "Partner with" is caught by the `startswith("partner")` rule. |
| Background cards aren't `can_be_commander` and would be missing from a pool | The `background` index is built from `type_line` regardless of `can_be_commander`; they're only ever offered as the **second** pick. |
| Legal-partner pool too large for the dropdown | Pools (~60 partners / ~30 backgrounds) are fine for the existing capped autocomplete (MAX_RESULTS=10). |
| Pairing breaks #19 scope params | A pairing is a normal slug; `get_commander_data(slug, tag=…)` composes the same way — no special-casing. |
| Doctor/Companion + 3-card combos | Explicitly out of scope (issue); `partner_kind` returns "" for them → no second input. |

---

## Out of Scope (per issue)
- Three+ commander / companion / "Doctor's companion" edge cases.
- Validating the pairing server-side beyond the restricted autocomplete (trust the
  client list; an illegal manual slug simply 404s via EDHRec).

---

## Acceptance Criteria

- [ ] After choosing commander 1, a partner-eligible commander reveals a second
      autocomplete restricted to legal pairings (partner / background / friends forever).
- [ ] Slept On scoring + EDHRec sections use EDHRec's combined pairing page.
- [ ] Color pool uses the union of both color identities (via the combined card).
- [ ] The pairing is one logical commander (combined slug) — downstream scoring unchanged.
- [ ] Header shows both commanders (via #18).
- [ ] `flake8 .` clean; `py_compile` clean.
- [ ] Smoke test: Tymna + Thrasios renders both commanders and a coherent WUBG Slept On list.
- [ ] Follows CLAUDE.md layering (bulk/edhrec fetch + classification, pure analysis, route wiring).
- [ ] GitHub Issue #21 criteria satisfied.
```
