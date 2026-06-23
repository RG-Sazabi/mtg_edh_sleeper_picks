# Plan: Deck-scoped Slept On scoring — force 100% inclusion + "in deck" badge

## Summary
When the commander page is reached with a `?deck=<id>` (from #33), re-fetch the Archidekt
deck, and tilt the feature-lift scoring toward what *that build* over-uses by treating the
deck's cards as 100%-inclusion in the **P_X** term — while keeping the color-identity
**baseline (P_B)** anchored to EDHRec's real inclusion/synergy. This is implemented with a
new, scoring-only `forced_inclusion` field honored by `analysis.compute_feature_stats`; the
displayed `edhrec_inclusion` is left untouched so deck cards aren't auto-hidden by the
inclusion-cap filter and the baseline trick stays intact. Every displayed card (Slept On +
EDHRec) gains an `in_deck` flag rendered as an "In deck" badge, mirroring the existing "In
EDHRec list" badge. Incomplete decks (≠100 cards) need no special handling. No change to
`score_card`/`score_cards` — the deck signal lives entirely in the weights.

## User Story
As a deckbuilder, I want sleeper picks scored against my actual Archidekt list with my current
cards still shown and marked "in deck", so that the suggestions reflect what my specific build
over-uses rather than the metagame average.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | MEDIUM–HIGH (carries the key scoring-formulation decision) |
| GitHub Issue | #34 |
| Systems Affected | `services/analysis.py`, `app.py` (commander route), `templates/_card.html`, `static/css/style.css` |
| Depends on | #33 (`services/archidekt.py` `get_deck(deck_id)` + the `?deck=<id>` route contract) |

---

## THE KEY DESIGN DECISION (resolves PRD Risk #1)

**Chosen formulation — option (b) done correctly, via a scoring-only `forced_inclusion`:**

The feature-lift model is, per card carrying feature `f`:
```
incl_c = i_{c,X}      = edhrec_inclusion              # commander's decks
base_c = i_{c,B(X)}   = edhrec_inclusion - synergy    # color-identity baseline
P_X(f) = avg incl_c ;  P_B(f) = avg base_c ;  weight(f) = P_X * log(P_X / P_B)
```
For a deck, we want the deck's actual picks to dominate **P_X** without disturbing **P_B**.
So we add an optional `forced_inclusion` to scoring cards and:
```
incl_c = forced_inclusion if present else edhrec_inclusion   # deck cards -> 1.0
base_c = edhrec_inclusion - synergy                          # UNCHANGED — real baseline
```
Deck cards in the recommended set thus push **P_X** up (toward 1.0) for the features they
carry, raising `lift` and `weight` for the deck's themes; **P_B** stays the true color
baseline, so the lift remains meaningful. Cards without `forced_inclusion` behave exactly as
today → **zero change to the non-deck commander flow**.

**Why not the obvious "just set `edhrec_inclusion = 1.0`":** it (a) corrupts `base_c =
inclusion − synergy` (baseline would become `1 − synergy`), and (b) the displayed inclusion
would exceed the inclusion-cap slider (default 10%), so the filter would **hide every deck
card** — directly contradicting "deck cards still suggested." Keeping `forced_inclusion`
separate from the displayed `edhrec_inclusion` avoids both.

**Scope of the override (MVP, primary path):** apply `forced_inclusion = 1.0` to cards in the
**existing scoring set** (EDHRec recommended cards) that are in the deck. This reweights
within the recommended set and is low-risk.
**Optional extension (same task, clearly marked):** also add deck cards that are absent from
the recommended set but present in the broader `incl_index` (their real baseline is known) as
extra scoring rows with `forced_inclusion = 1.0`, enriched with `type_line`/otags from the
bulk store. Ship the primary path first; add the extension if the deck signal feels weak.

This formulation must be written into `services/analysis.py` next to the existing model
comment (AC requirement).

---

## Patterns to Follow

### The scoring loop to extend (one localized change)
```python
# SOURCE: services/analysis.py — compute_feature_stats, the per-card accumulation loop
incl = card.get("edhrec_inclusion", 0.0) or 0.0
syn = card.get("edhrec_synergy", 0.0) or 0.0
incl_c = max(incl, eps)            # <- becomes max(forced_inclusion or incl, eps)
base_c = max(incl - syn, eps)      # <- UNCHANGED
```

### Existing "in EDHRec list" badge (mirror for "in deck")
```jinja
{# SOURCE: templates/_card.html (slept_on_card macro) — in_edhrec badge span #}
{% if card.in_edhrec %}<span class="edhrec-badge" title="...">In EDHRec list</span>{% endif %}
```

### Per-card flag set in the route (mirror for in_deck)
```python
# SOURCE: app.py — slept_on loop sets c["in_edhrec"] = normalize_name(c["name"]) in edhrec_names
```

### Deck access (from #33)
```python
# SOURCE: services/archidekt.py (#33) — parse_deck_id(url), get_deck(deck_id) -> {deck_id, commander_names, card_names}
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/analysis.py` | UPDATE | `compute_feature_stats` honors `forced_inclusion` for P_X (P_B unchanged); document the deck formulation |
| `app.py` | UPDATE | Commander route: read `?deck=`, fetch deck, set `forced_inclusion` on scoring cards, set `in_deck` on all displayed cards |
| `templates/_card.html` | UPDATE | "In deck" badge in `slept_on_card` and `card_item` macros |
| `static/css/style.css` | UPDATE | `.deck-badge` styling |

No new dependencies. `archidekt` import already added to `app.py` in #33.

---

## Tasks

### Task 1: Honor `forced_inclusion` in `compute_feature_stats`
- **File**: `services/analysis.py`
- **Action**: UPDATE
- **Implement**:
  - In the per-card loop of `compute_feature_stats`, change `incl_c` to prefer a
    scoring-only override:
    ```python
    forced = card.get("forced_inclusion")
    incl_c = max(forced if forced is not None else incl, eps)
    base_c = max(incl - syn, eps)  # unchanged — real color-identity baseline
    ```
  - Add a comment block (next to the module's existing feature-lift model docstring) titled
    e.g. "Deck-scoped scoring (issue #34)" capturing the formulation from the section above:
    deck membership forces P_X→1.0 via `forced_inclusion`; P_B stays the real
    `inclusion − synergy`; the displayed `edhrec_inclusion` is deliberately NOT overwritten.
  - Note in `compute_feature_stats`' docstring that `forced_inclusion` (when present) drives
    P_X. Keep the function pure.
- **Mirror**: the existing `incl_c`/`base_c` lines; backward-compatible (no override → today's behavior).
- **Validate**: `flake8 services/analysis.py && python -m py_compile services/analysis.py`

### Task 2: Deck scope in the commander route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  - Read the scope param near the others (line ~55): `deck_id = request.args.get("deck", "")`.
  - After `scoring_cards` is resolved (line ~144) and the `incl_index` is available, resolve
    the deck and apply the override **before** `compute_feature_stats` (line ~152):
    ```python
    deck_names: set[str] = set()
    if deck_id:
        deck = archidekt.get_deck(deck_id)
        if deck:
            deck_names = {analysis.normalize_name(n) for n in deck["card_names"]}
            for c in scoring_cards:
                if analysis.normalize_name(c["name"]) in deck_names:
                    c["forced_inclusion"] = 1.0
            # OPTIONAL extension: add deck cards present in incl_index but not in
            # scoring_cards as extra forced-inclusion rows (enrich type_line/otags via
            # scryfall.get_cards_collection, set edhrec_inclusion/synergy from incl_index).
        else:
            app.logger.warning("deck %s could not be fetched; rendering commander average", deck_id)
    ```
    (`feature_stats = analysis.compute_feature_stats(scoring_cards)` then picks up the override
    automatically — no change to that call.)
  - Set the `in_deck` flag on every displayed card. Mirror the existing `in_edhrec` writes:
    in the `slept_on` enrichment loop add `c["in_deck"] = analysis.normalize_name(c["name"]) in
    deck_names`; do the same in the `edhrec_cards` and `featured_cards` enrichment loops.
  - Degrade gracefully: a missing/invalid `deck` param or a failed fetch leaves `deck_names`
    empty → the page renders the normal commander-average analysis (no 500, no badges).
- **Mirror**: `app.py` scope-param reads (lines 55-57); the `in_edhrec` flag write; the
  `forced_inclusion` is consumed by Task 1.
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 3: "In deck" badge in the card macros
- **File**: `templates/_card.html`
- **Action**: UPDATE
- **Implement**: In **both** `slept_on_card` and `card_item`, add next to the name (and
  alongside the existing `in_edhrec` badge in `slept_on_card`):
  ```jinja
  {% if card.in_deck %}<span class="deck-badge" title="This card is in your linked Archidekt deck.">In deck</span>{% endif %}
  ```
- **Mirror**: the `in_edhrec` badge span already in `slept_on_card`.
- **Validate**: smoke test (Task 5).

### Task 4: `.deck-badge` CSS
- **File**: `static/css/style.css`
- **Action**: UPDATE
- **Implement**: Add a `.deck-badge` rule near `.edhrec-badge` (reuse its sizing/shape; pick a
  distinct accent colour so "In deck" reads differently from "In EDHRec list").
- **Validate**: badge renders legibly in both tabs.

### Task 5: Validate + manual smoke test
- **File**: — (verification only)
- **Action**: VALIDATE
- **Implement**: Run the validation sequence, then `python app.py`:
  - From the landing page paste `https://archidekt.com/decks/1/` (Thelon of Havenwood, via
    #33) → lands on `/commander/<slug>?deck=1`.
  - Confirm cards in that deck show the **"In deck"** badge in both Slept On and EDHRec tabs.
  - Confirm the Slept On ordering **differs** from the same commander **without** `?deck=1`
    (open both) — the deck tilt should move scores. Use Diagnostics to eyeball that
    deck-emphasised features have higher P(X)/weight.
  - Confirm deck cards are **not** auto-hidden by the default 10% inclusion cap (their
    displayed inclusion is the real EDHRec value, not 100%).
  - Open a commander page **without** `?deck=` → identical to before (no regression, no badges).
- **Validate**: see Validation Sequence.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/analysis.py services/archidekt.py
# Manual smoke (per CLAUDE.md): python app.py
#   - https://archidekt.com/decks/1/ -> ?deck=1, "In deck" badges, deck-tilted Slept On
#   - same commander without ?deck= -> unchanged
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Overwriting `edhrec_inclusion` would corrupt the baseline AND hide deck cards under the inclusion cap | Use a **separate `forced_inclusion`** field consumed only by `compute_feature_stats`; never touch displayed `edhrec_inclusion`. (Core design decision.) |
| Non-deck commander pages regress | The override is opt-in (`forced_inclusion` absent → identical math). Task 5 verifies the no-`?deck=` page is unchanged. |
| Deck fetched in #33 but deleted/failed by the time the commander route runs | `get_deck` returns `None` → `deck_names` stays empty → commander-average render + a logged warning; never a 500. |
| Deck signal feels too weak (most pet cards aren't in the recommended set) | Ship the primary override first; enable the documented `incl_index` extension in Task 2 if needed. |
| Deck + theme/budget/bracket interaction undefined | MVP applies the override to the resolved `scoring_cards` (base weights tilted by the deck); deck+tag combination is out of scope. |

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] `flake8 .` clean; `python -m py_compile app.py services/analysis.py` clean
- [ ] `analysis.py` additions remain pure (no I/O); HTTP stays in `services/archidekt.py`
- [ ] No test suite (per CLAUDE.md) — manual smoke test passes
- [ ] GitHub Issue #34 criteria satisfied:
  - [ ] Deck cards treated as inclusion = 100% in the scoring path (via `forced_inclusion`)
  - [ ] EDHRec supplies the color-identity baseline; the deck drives over-use
  - [ ] Deck cards still suggested, tagged with an "In deck" badge (reusing the `in_edhrec` pattern)
  - [ ] Incomplete deck (≠100 cards) still renders a full analysis
  - [ ] Chosen P_X/P_B formulation implemented and **documented** in `services/analysis.py`
  - [ ] Deck-scoped scores differ from the bare-commander view; no-`?deck=` flow unchanged

---

## Out of Scope (deferred)
- A "hide cards already in my deck" filter toggle
- Deck caching across requests
- Deck + theme/budget/bracket combined scoping
- Deck sources other than Archidekt
