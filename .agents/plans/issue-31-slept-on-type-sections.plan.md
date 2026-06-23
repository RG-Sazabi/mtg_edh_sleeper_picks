# Plan: Split Slept On into Top 10 + per-card-type sections (server + template)

## Summary
Today the Slept On tab is a single flat grid (`#slept-on-grid`) of the top-N scored
cards. This change keeps the existing scoring untouched and adds a **presentation-only**
split: an overall **Top 10** section plus seven independent per-card-type sections
(Creatures, Instants, Sorceries, Enchantments, Artifacts, Lands, Planeswalkers). A new
pure helper `analysis.partition_by_type()` buckets the already-scored, already-enriched
Slept On list into the seven types using the existing `card_features()` output, so
multi-type cards (e.g. an artifact creature) land in every matching section. The route
passes the Top 10 slice + the seven buckets to the template, which renders one grid per
section via a new shared Jinja macro. The current `#slept-on-grid` id is preserved on the
Top 10 grid so `static/js/filters.js` keeps working unchanged — generalizing client
filtering across all grids is the follow-up issue (#32).

## As-Built Deviations (approved — supersedes the plan body below)
The implementation diverged from this plan at the user's direction. The shipped behavior:

1. **Creatures slot only under Creatures.** A creature — including an artifact/enchantment
   creature — appears **only** in the Creatures section, not also in Artifacts/Enchantments.
   Other multi-type cards still appear under every matching section (e.g. an artifact land
   in both Artifacts and Lands). This intentionally overrides the original "appear in every
   matching section" requirement. See `partition_by_type` (`services/analysis.py`), which
   carries an `is_creature` guard.
2. **`partition_by_type(cards, cap=None)` gained a `cap` parameter**, and sections draw from
   the **full** scored list capped per-section at `SLEPT_ON_SECTION_CAP = 100`, rather than
   partitioning a globally `[:SLEPT_ON_RENDER_CAP=200]`-capped list. This lets a sparse type
   fill up to the cap. `app.py` no longer slices `slept_on`; it enriches only the displayed
   union (Top 10 + section members), deduped by `id()`.
3. **Per-grid filtering + N-limit landed here, not in #32.** `static/js/filters.js` already
   iterates all `.slept-on-grid` for price/pauper/inclusion + N-limit. Still pending for #32:
   generalizing `reorderSleptOn` to every grid and the Top 10 filter-refill (the Top 10 grid
   still renders only `top_overall`'s 10 nodes).

The task list below is the original intent, kept for history; where it conflicts with the
three points above, the as-built behavior wins.

## User Story
As a deckbuilder, I want the Slept On picks split by card type with one overall Top 10,
so that I can quickly find sleeper cards for the exact slot I'm filling and still see the
strongest picks at a glance.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | LOW–MEDIUM |
| GitHub Issue | #31 |
| Systems Affected | `services/analysis.py` (pure), `app.py` (route), `templates/commander.html`, `templates/_card.html` |

---

## Patterns to Follow

### Pure "sections as list-of-dicts" return shape
Mirror how EDHRec featured sections are built and consumed.
```python
# SOURCE: services/edhrec.py:214-238  (featured_sections_from_data)
sections: list[dict] = []
for tag in _FEATURED_TAGS:
    ...
    sections.append({"tag": tag, "header": header, "cards": cards})
return sections
```
```jinja
{# SOURCE: templates/commander.html:84-89  (consuming the list with headers) #}
{% for sec in featured %}
<h3>{{ sec.header }}</h3>
<div class="card-grid">
  {% for card in sec.cards %}{{ card_item(card) }}{% endfor %}
</div>
{% endfor %}
```

### Feature derivation (types come from here — do not re-parse type_line)
```python
# SOURCE: services/analysis.py:48-71  (card_features)
# "Legendary Creature — Phyrexian Horror" -> ["type:Creature", "sub:Phyrexian", ...]
# Supertypes (Legendary/Basic/Snow/...) are already filtered out (_SUPERTYPES).
```

### Existing Slept On card markup (to be extracted verbatim into a macro)
```jinja
{# SOURCE: templates/commander.html:60-77 — bespoke slept-on card (badge, js-score,
   data-features, tags line). NOT the same as _card.html card_item. #}
```

### Module-level pure helpers + constants
```python
# SOURCE: services/analysis.py:33-34  (_SUPERTYPES constant)
# SOURCE: services/analysis.py:192-221 (score_cards: pure, returns new sorted list,
#         does not mutate inputs)
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/analysis.py` | UPDATE | Add `SLEPT_ON_TYPE_SECTIONS` constant + pure `partition_by_type()` helper |
| `templates/_card.html` | UPDATE | Add `slept_on_card(card)` macro = current Slept On card markup, extracted for reuse across 8 grids |
| `app.py` | UPDATE | Compute `top_overall` (first 10) + `type_sections`; pass both to the template |
| `templates/commander.html` | UPDATE | Replace the single grid with Top 10 grid + 7 type-section grids, all using the macro; keep `id="slept-on-grid"` on Top 10 for JS compat |

No new files. No new dependencies.

---

## Design Notes / Decisions

1. **Partition the already-capped, already-enriched list.** `app.py` already produces
   `slept_on = analysis.score_cards(...)[:SLEPT_ON_RENDER_CAP]` (200) and then enriches
   each card with `features` + `in_edhrec` (lines 146-170). Partition **that** list. The
   card dicts are shared by reference, so a card appearing in Top 10 and in a type section
   is the same enriched dict — no double-enrichment, no extra work, and the `features` /
   `in_edhrec` loop stays exactly as-is. Top 10 = `slept_on[:10]`.

2. **Render order = score order, preserved for free.** `score_cards` already returns the
   list sorted by `buzzword_score` desc. `partition_by_type` iterates that list in order
   and appends, so each bucket is independently sorted without re-sorting.

3. **Multi-type cards appear in every matching section** — a card is appended to each
   bucket whose `type:<Name>` it carries. Cards with none of the seven types (e.g. a bare
   Battle) simply land in no bucket but are still eligible for Top 10. (AC satisfied.)

4. **Do NOT break the page (client work is #32).** `filters.js:25` reads
   `getElementById('slept-on-grid')` and calls `.querySelectorAll` on it inside
   `applyFilters()`, which runs before the tabs/copy listeners are wired — a null there
   would throw and break the whole page. Mitigation: keep `id="slept-on-grid"` on the
   **Top 10** grid and give **all eight** grids a shared `class="slept-on-grid"`. Existing
   JS keeps filtering the Top 10 grid (≤10 cards, harmless under the default N=50/inclusion
   sliders); type sections render unfiltered until #32 migrates the JS to the class
   selector and removes the id. The Diagnostics live-rescore loop already targets
   `.card-item[data-features]`, so type-section cards get correct scores + tooltips for free.

5. **Render all seven sections** (even if a bucket is empty for a given commander) so the
   AC "seven per-type sections render" holds literally; an empty grid under a header is
   acceptable and rare for multi-type commanders.

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Add `SLEPT_ON_TYPE_SECTIONS` + `partition_by_type()` to analysis
- **File**: `services/analysis.py`
- **Action**: UPDATE
- **Implement**:
  - Add a module constant near `_SUPERTYPES` (after line 34):
    ```python
    # Ordered (label, card-type) pairs for the per-type Slept On sections. Multi-type
    # cards appear under every matching label; types outside this list are absent from
    # the sections but remain eligible for the overall Top 10.
    SLEPT_ON_TYPE_SECTIONS = [
        ("Creatures", "Creature"),
        ("Instants", "Instant"),
        ("Sorceries", "Sorcery"),
        ("Enchantments", "Enchantment"),
        ("Artifacts", "Artifact"),
        ("Lands", "Land"),
        ("Planeswalkers", "Planeswalker"),
    ]
    ```
  - Add a pure helper (place it after `score_cards`, ~line 221):
    ```python
    def partition_by_type(cards: list[dict]) -> list[dict]:
        """
        Bucket already-scored Slept On cards into the per-type sections.

        Returns one dict per entry in ``SLEPT_ON_TYPE_SECTIONS`` (stable order)::

            {"label": "Creatures", "type": "Creature", "cards": [...]}

        A card is added to every section whose ``type:<Name>`` it carries (so an
        artifact creature appears under both Artifacts and Creatures); cards with none
        of the seven types appear in no section. Input order is preserved within each
        bucket, so passing a score-desc list yields score-desc sections. Pure: the same
        card dicts are referenced (not copied) and never mutated.
        """
        buckets: dict[str, list[dict]] = {
            label: [] for label, _ in SLEPT_ON_TYPE_SECTIONS
        }
        for card in cards:
            types = {f for f in card_features(card) if f.startswith("type:")}
            for label, type_name in SLEPT_ON_TYPE_SECTIONS:
                if f"type:{type_name}" in types:
                    buckets[label].append(card)
        return [
            {"label": label, "type": type_name, "cards": buckets[label]}
            for label, type_name in SLEPT_ON_TYPE_SECTIONS
        ]
    ```
- **Mirror**: `services/analysis.py:192-221` (pure, non-mutating, returns new list); constant style `services/analysis.py:33-34`.
- **Validate**: `flake8 services/analysis.py && python -m py_compile services/analysis.py`

### Task 2: Extract the Slept On card markup into a reusable macro
- **File**: `templates/_card.html`
- **Action**: UPDATE
- **Implement**: Add a new macro `slept_on_card(card)` **after** the existing `card_item`
  macro (after line 19). Copy the bespoke Slept On card markup verbatim from
  `templates/commander.html:60-77` (the `data-*` attributes, the `<img>`, the
  `in_edhrec` badge `<span>`, the `js-score` span, inclusion/price/rarity spans, and the
  `Tags:` line). This is the single source for the per-card Slept On markup so the eight
  grids stay DRY and future badge work (#34's "in deck") edits one place.
- **Mirror**: `templates/_card.html:1-19` (existing `card_item` macro structure).
- **Validate**: n/a (template) — verified via the smoke test in Task 5.

### Task 3: Compute Top 10 + type sections in the route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  - Add a module constant near `SLEPT_ON_RENDER_CAP` (line 13):
    `TOP_OVERALL_N = 10  # the single overall Slept On section`
  - After the existing Slept On enrichment loop (after line 170, where `slept_on` cards
    get `features` + `in_edhrec`), compute:
    ```python
    top_overall = slept_on[:TOP_OVERALL_N]
    type_sections = analysis.partition_by_type(slept_on)
    ```
  - Add `top_overall=top_overall` and `type_sections=type_sections` to the
    `render_template("commander.html", ...)` kwargs (lines 172-187). Keep `slept_on=...`
    in the kwargs too (harmless; can be dropped in #32 if unused after the template change
    — but leave it for this issue to minimize churn).
- **Mirror**: existing kwargs passing at `app.py:172-187`; `featured`/`featured_cards`
  precedent at `app.py:87-88`.
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 4: Render Top 10 + seven type grids in the template
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**:
  - Extend the macro import on line 2 to also import the new macro:
    `{% from "_card.html" import card_item, slept_on_card %}`
  - Replace the single grid block (lines 58-79, the `<div class="card-grid"
    id="slept-on-grid"> … {% for card in slept_on %} … </div>`) with:
    - A **Top 10** subsection: an `<h3>Top 10</h3>` and a grid
      `<div class="card-grid slept-on-grid" id="slept-on-grid">` looping
      `{% for card in top_overall %}{{ slept_on_card(card) }}{% endfor %}`.
      (Keep `id="slept-on-grid"` here so `filters.js` is unaffected; add the
      `slept-on-grid` **class** for #32's future class-based selector.)
    - Then loop the type sections:
      ```jinja
      {% for sec in type_sections %}
      <h3>{{ sec.label }}</h3>
      <div class="card-grid slept-on-grid" data-type="{{ sec.type }}">
        {% for card in sec.cards %}{{ slept_on_card(card) }}{% endfor %}
      </div>
      {% endfor %}
      ```
  - Leave the existing `#slept-on-controls` (N slider / inclusion cap, lines 52-57) where
    it is; it continues to drive the Top 10 grid via existing JS this issue.
- **Mirror**: section+header+grid loop at `templates/commander.html:84-95` (EDHRec
  featured / category sections).
- **Validate**: n/a (template) — verified in Task 5.

### Task 5: Validate + manual smoke test
- **File**: — (verification only)
- **Action**: VALIDATE
- **Implement**:
  - Run the full validation sequence (below).
  - `python app.py`, search "Atraxa, Praetors' Voice", open the Slept On tab; confirm:
    a **Top 10** section + the seven type sections render with cards; a known
    artifact-creature (e.g. **Solemn Simulacrum**, if present) shows under **both**
    Creatures and Artifacts; the page is not JS-broken (tabs switch, clicking a card
    copies its name, Diagnostics toggles still re-score visible cards).
- **Validate**: see Validation Sequence.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/analysis.py
# Manual smoke (per CLAUDE.md): python app.py -> search "Atraxa, Praetors' Voice"
```

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] `flake8 .` clean
- [ ] `python -m py_compile app.py services/analysis.py` clean
- [ ] No test suite (per CLAUDE.md) — manual Atraxa smoke test passes
- [ ] Follows existing patterns (pure analysis helper; list-of-dicts sections; macro reuse)
- [ ] GitHub Issue #31 criteria satisfied:
  - [ ] Single **Top 10** section shows the 10 highest-scoring picks overall
  - [ ] Seven per-type sections render, ranked independently
  - [ ] A card may appear in both the Top 10 and its type section(s)
  - [ ] A multi-type non-creature card appears in every matching type section; creatures slot only under Creatures (approved deviation — see As-Built Deviations)
  - [ ] Cards outside the seven types stay eligible for Top 10, absent from type sections
  - [ ] Commander-name flow (Atraxa) renders without regression (page JS intact)

---

## Out of Scope (deferred to #32)
- Generalizing `filters.js` to filter/N-limit across all `.slept-on-grid` grids
- The shared N slider controlling type sections; Top 10 fixed at 10 via JS
- Removing the transitional `id="slept-on-grid"` once JS targets the class
- Per-section header CSS polish (add minimal/none here; #32 owns section styling)
