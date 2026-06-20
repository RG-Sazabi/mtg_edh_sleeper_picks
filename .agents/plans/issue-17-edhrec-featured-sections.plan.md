# Plan: New / High Synergy / Top display-only sections on the EDHRec tab

## Summary
The real EDHRec commander page leads with "New Cards", "High Synergy Cards", and
"Top Cards" rows above the per-type categories. Our EDHRec tab omits them: issue #15
deliberately has `edhrec.cards_from_data()` **skip** the meta cardlists
(`newcards / highsynergycards / topcards / gamechangers`) so they don't pollute the
type-category grouping or the scoring set — leaving their display to this issue. Here
we extract those meta lists into ordered display-only sections, enrich + score their
cards for rendering (without adding them to the Slept On scoring dataset or feature
weights), extract the duplicated `card-item` markup into a reusable Jinja macro, and
render the new sections at the top of the EDHRec tab using that macro.

## User Story
As a Brewer, I want New / High Synergy / Top sections on the EDHRec tab, so that the
page matches what I see on the real EDHRec commander page.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | MEDIUM |
| GitHub Issue | #17 |
| Systems Affected | `services/edhrec.py`, `app.py` (commander route), `templates/commander.html`, new `templates/_card.html` |
| **Blocked by** | **#15** (provides `get_commander_data`, `_card_from_cardview`, `_META_TAGS`, and the meta-skip in `cards_from_data`) |

> **Sequencing:** Implement **after #15**. This plan calls `edhrec.get_commander_data`,
> `edhrec._card_from_cardview`, and assumes `cards_from_data` already excludes the meta
> tags. If #15 is not yet merged, implement its Tasks 2–3 first.

---

## Spike Findings (verified 2026-06-20, reconciled with the #15 plan)

- EDHRec page container `json_dict.cardlists` includes meta lists with `tag` ∈
  `{newcards, highsynergycards, topcards, gamechangers}` and `header` ∈
  `{"New Cards", "High Synergy Cards", "Top Cards", "Game Changers"}`. Atraxa counts:
  New 5, High Synergy 10, Top 10, Game Changers 10. Cardviews carry the same fields as
  type-category cards (`name, inclusion, num_decks, potential_decks, synergy`).
- **AC scope = New / High Synergy / Top** (three). `gamechangers` is optional and not
  required by the AC; this plan wires the three required sections and notes how to add
  Game Changers in one line if desired.
- Meta-list cards are largely **duplicates** of type-category cards (same card, same
  per-commander inclusion/synergy). Showing them again in a featured row is the desired
  EDHRec-parity behavior — they are display-only.
- The `card-item` markup is **duplicated inline**: Slept On at
  `templates/commander.html:29-46`, EDHRec categories at `:57-73`. No macro/partial
  exists yet. The issue asks to "reuse the existing card display partial used by the
  other category rows" → extract a macro and use it for the EDHRec categories + the new
  featured sections.
- `static/js/filters.js:12` selects `#edhrec-section .card-item` for the price/pauper
  filter, and `recomputeScores()` (`:25-34`) re-scores **every** `.card-item[data-features]`.
  Putting featured sections **inside `#edhrec-section`** makes them inherit price/pauper
  filtering and live re-score with no JS changes. The tab switcher (`:134-145`) and copy
  handler (`:175-182`) operate on existing selectors and need no change.

---

## Patterns to Follow

### Pure cardlist extraction in edhrec.py (#15 helper to reuse)
```python
# SOURCE: services/edhrec.py (added by #15) — _card_from_cardview / cards_from_data
# _card_from_cardview(cv, category) -> scoring-shaped dict:
#   {"name","edhrec_category","edhrec_synergy","edhrec_inclusion","otags":[],
#    "type_line":"","price_usd":None,"rarity":"","image_uri":"","buzzword_score":0.0}
# cards_from_data(data) iterates data["cardlists"], SKIPS tags in _META_TAGS,
# dedupes by name. Mirror its iteration for the meta lists.
```

### Route enrichment + display scoring (mirror exactly)
```python
# SOURCE: app.py:53-57  (Scryfall enrichment)
scryfall.warm_up()
card_details = scryfall.get_cards_collection([c["name"] for c in edhrec_cards])
for card in edhrec_cards:
    card.update(card_details.get(card["name"], scryfall._empty_card_details()))

# SOURCE: app.py:76-78  (display score on the same weights — NOT added to the dataset)
for c in edhrec_cards:
    c["features"] = analysis.card_features(c)
    c["buzzword_score"] = analysis.score_card(c, weights)
```

### Card-item markup to factor into a macro
```html
<!-- SOURCE: templates/commander.html:57-73 (EDHRec category card) -->
<div class="card-item" data-name=".." data-price=".." data-rarity=".."
     data-inclusion=".." data-score=".." data-features="..">
  <img src=".." alt=".." loading="lazy">
  <div class="card-info">
    <strong>{{ card.name }}</strong>
    <span class="js-score">Score: {{ card.buzzword_score | round(3) }}</span>
    <span>Synergy: {{ (card.edhrec_synergy * 100) | round(1) }}%</span>
    <span>Inclusion: {{ (card.edhrec_inclusion * 100) | round(1) }}%</span>
    <span>Price: {% if card.price_usd %}${{ "%.2f" | format(card.price_usd) }}{% else %}N/A{% endif %}</span>
    <span>{{ card.rarity | capitalize }}</span>
  </div>
</div>
```

### Jinja import/macro usage (standard)
```html
{% from "_card.html" import card_item %}
{{ card_item(card) }}
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `templates/_card.html` | CREATE | Reusable `card_item(card, show_synergy=true)` macro (DRY for EDHRec categories + featured sections). |
| `services/edhrec.py` | UPDATE | Add `featured_sections_from_data(data)` returning ordered non-empty New/High Synergy/Top sections. |
| `app.py` | UPDATE | Build featured sections, enrich + display-score their cards, pass to template. |
| `templates/commander.html` | UPDATE | Render featured sections at top of `#edhrec-section`; refactor category rows to the macro. |

No new dependencies.

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Extract a reusable card-item Jinja macro
- **File**: `templates/_card.html`
- **Action**: CREATE
- **Implement**: Create a macro that reproduces the EDHRec category card markup
  (`commander.html:57-73`) exactly, parameterized:
  ```jinja
  {% macro card_item(card, show_synergy=true) %}
  <div class="card-item"
       data-name="{{ card.name }}"
       data-price="{{ card.price_usd if card.price_usd is not none else 9999 }}"
       data-rarity="{{ card.rarity }}"
       data-inclusion="{{ (card.edhrec_inclusion * 100) | int }}"
       data-score="{{ card.buzzword_score }}"
       data-features="{{ card.features | join('|') }}">
    <img src="{{ card.image_uri }}" alt="{{ card.name }}" loading="lazy">
    <div class="card-info">
      <strong>{{ card.name }}</strong>
      <span class="js-score">Score: {{ card.buzzword_score | round(3) }}</span>
      {% if show_synergy %}<span>Synergy: {{ (card.edhrec_synergy * 100) | round(1) }}%</span>{% endif %}
      <span>Inclusion: {{ (card.edhrec_inclusion * 100) | round(1) }}%</span>
      <span>Price: {% if card.price_usd %}${{ "%.2f" | format(card.price_usd) }}{% else %}N/A{% endif %}</span>
      <span>{{ card.rarity | capitalize }}</span>
    </div>
  </div>
  {% endmacro %}
  ```
  Keep the attribute set identical so `filters.js` (`data-price/-rarity/-inclusion/-score/-features`)
  keeps working. (Slept On stays inline — it has the `in_edhrec` badge + Tags row; out of scope to refactor here.)
- **Mirror**: `templates/commander.html:57-73`.
- **Validate**: file renders without Jinja syntax errors (covered by Task 6 smoke test).

### Task 2: Add `featured_sections_from_data` to edhrec.py
- **File**: `services/edhrec.py`
- **Action**: UPDATE
- **Implement**:
  1. Add an ordered constant for the featured (meta) lists:
     ```python
     # Display-only "featured" rows shown at the top of the EDHRec tab, in EDHRec's
     # order. Subset of _META_TAGS (gamechangers intentionally omitted per AC #17).
     _FEATURED_TAGS = ("newcards", "highsynergycards", "topcards")
     ```
  2. Add a pure function:
     ```python
     def featured_sections_from_data(data: dict) -> list[dict]:
         """
         Ordered display-only sections (New / High Synergy / Top) from the EDHRec
         page container. Each section: {"tag", "header", "cards": [<scoring dict>]}.
         Empty/missing lists are omitted so the template degrades gracefully. These
         cards are NOT part of the scoring dataset (see cards_from_data, which skips
         these tags) — they are rendered for parity only.
         """
     ```
     Build a `{tag: cardlist}` map from `data.get("cardlists", [])`, then for each tag
     in `_FEATURED_TAGS` (preserving order) take its `cardviews`, build cards via the
     #15 helper `_card_from_cardview(cv, header)`, and append a section only if it has
     cards. Return `[]` if `data` is falsy.
- **Mirror**: `services/edhrec.py` `cards_from_data` iteration + `_card_from_cardview`
  (both added by #15).
- **Validate**: `flake8 services/edhrec.py && python -m py_compile services/edhrec.py`

### Task 3: Wire featured sections into the route (enrich + display-score)
- **File**: `app.py`
- **Action**: UPDATE
- **Implement** (post-#15 route in `commander(slug)`):
  1. After `edhrec_cards = edhrec.cards_from_data(data)`, build:
     ```python
     featured = edhrec.featured_sections_from_data(data)
     ```
  2. Enrich both sets with one Scryfall call. Replace the single-list enrichment
     (`app.py:55-57`) so it covers featured cards too:
     ```python
     featured_cards = [c for sec in featured for c in sec["cards"]]
     names = [c["name"] for c in edhrec_cards] + [c["name"] for c in featured_cards]
     card_details = scryfall.get_cards_collection(names)
     for card in edhrec_cards + featured_cards:
         card.update(card_details.get(card["name"], scryfall._empty_card_details()))
     ```
  3. After `weights` is computed, add the SAME display-scoring loop used for
     `edhrec_cards` (mirror `app.py:76-78`) to the featured cards — for display only;
     they are **not** appended to `edhrec_cards` and do **not** enter
     `compute_feature_stats`/`score_cards`:
     ```python
     for c in featured_cards:
         c["features"] = analysis.card_features(c)
         c["buzzword_score"] = analysis.score_card(c, weights)
     ```
  4. Pass `featured=featured` into `render_template("commander.html", ...)`.
- **Mirror**: `app.py:53-57` (enrichment), `app.py:76-78` (display scoring).
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 4: Render featured sections + refactor categories to the macro
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**:
  1. At the top of the file's `{% block content %}` add the macro import:
     `{% from "_card.html" import card_item %}`.
  2. Inside `#edhrec-section` (`:51`), **before** the category loop, render featured
     sections (only when present so it degrades gracefully):
     ```jinja
     {% for sec in featured %}
     <h3>{{ sec.header }}</h3>
     <div class="card-grid">
       {% for card in sec.cards %}{{ card_item(card) }}{% endfor %}
     </div>
     {% endfor %}
     ```
     (When `featured` is empty the loop renders nothing — no empty headers.)
  3. Refactor the existing category loop body (`:56-73`) to call the macro:
     ```jinja
     {% for category, cat_cards in edhrec_cards | groupby("edhrec_category") %}
     <h3>{{ category }}</h3>
     <div class="card-grid">
       {% for card in cat_cards %}{{ card_item(card) }}{% endfor %}
     </div>
     {% endfor %}
     ```
  Keep the `#edhrec-section` wrapper, `<h2>EDHRec Recommendations</h2>`, Slept On, and
  Diagnostics sections unchanged.
- **Mirror**: `templates/commander.html:51-77`.
- **Validate**: page renders (Task 6).

### Task 5: (Optional, not required by AC) Game Changers
- **File**: `services/edhrec.py`
- **Action**: UPDATE (optional)
- **Implement**: To also show EDHRec's "Game Changers" row, append `"gamechangers"` to
  `_FEATURED_TAGS`. No other change needed (it flows through Tasks 3–4). Leave out if
  matching the AC's three sections exactly.
- **Validate**: same as Task 2.

### Task 6: Manual smoke test
- **File**: n/a
- **Action**: verify
- **Implement**:
  1. `python app.py`, open `/commander/atraxa-praetors-voice`, click the **EDHRec** tab.
  2. Confirm **New Cards / High Synergy Cards / Top Cards** rows render at the top with
     images, synergy %, inclusion %, price, rarity — High Synergy matching EDHRec's
     highlighted cards.
  3. Confirm the per-type categories still render below them.
  4. Confirm price-cap / pauper filters hide featured cards too, and Diagnostics toggles
     re-score them (they live inside `#edhrec-section`).
  5. Confirm the **Slept On** tab and its scoring are unchanged (featured cards did not
     enter the scoring set).
  6. Verify a commander with a missing/empty meta list simply omits that row (no empty
     header, no error).
- **Validate**: visual; both featured + category rows populated; Slept On unaffected.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
python app.py   # load /commander/atraxa-praetors-voice -> EDHRec tab
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Implemented before #15 → `get_commander_data`/`_card_from_cardview` missing | Marked **Blocked by #15**; sequencing note up top. Verify those symbols exist before starting. |
| Featured cards accidentally inflate Slept On scoring | They are enriched/scored in a **separate** `featured_cards` list, never appended to `edhrec_cards`, and never passed to `compute_feature_stats`/`score_cards`. Task 6 step 5 verifies. |
| Duplicate `data-name` across featured + category copies of a card | No element IDs are used; copy/filter/re-score all key off classes + data-attrs, so duplicates are harmless (both copies behave identically). |
| Macro refactor changes category markup subtly, breaking `filters.js` | Macro reproduces the exact attribute set (`data-price/-rarity/-inclusion/-score/-features`); Task 6 step 4 confirms filters/toggles still work. |
| Empty meta list renders a stray header | `featured_sections_from_data` omits empty sections; template loops only over returned sections. |

---

## Acceptance Criteria

- [ ] EDHRec tab renders New / High Synergy / Top sections as their own card rows with
      image, name, synergy %, inclusion %, price, rarity.
- [ ] Sections are display-only — Slept On scoring dataset and feature weights are
      unchanged (featured cards are not added to `edhrec_cards` / scoring).
- [ ] Sections are omitted gracefully when EDHRec returns no data for them.
- [ ] Category rows and featured rows share one `card_item` macro (DRY).
- [ ] `flake8 .` clean; `py_compile` clean.
- [ ] Smoke test: Atraxa EDHRec tab shows a High Synergy row matching EDHRec.
- [ ] Follows CLAUDE.md layering (fetch/shape in `edhrec.py`, route wiring in `app.py`,
      display-only templates).
- [ ] GitHub Issue #17 criteria satisfied.
```
