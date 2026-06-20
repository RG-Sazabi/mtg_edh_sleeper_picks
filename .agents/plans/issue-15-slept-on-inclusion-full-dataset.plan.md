# Plan: Full per-commander EDHRec dataset — fix Slept On inclusion % and score on all-cards baseline

## Summary
The Slept On tab shows every card at `0%` inclusion because color-pool candidates
are created with `edhrec_inclusion=0.0` (`services/scryfall.py:get_color_identity_pool`)
and nothing ever joins EDHRec's real per-commander inclusion back onto them. At the
same time, the EDHRec recommendation list (and therefore the feature-weight scoring)
is built from `pyedhrec`'s `get_commander_cards`, which depends on a fragile,
hard-coded Next.js `build_id` and only returns whatever that path yields.

This change reroutes the commander fetch to the **stable** EDHRec endpoint we already
use for `get_commander_info` — `https://json.edhrec.com/pages/commanders/<slug>.json`
— whose `container.json_dict.cardlists` carries **all 13 cardlists** (New, High
Synergy, Top, Game Changers, plus every type category) with `inclusion`,
`potential_decks`, and `synergy` per card. We fetch the page once, extract (a) the
commander info, (b) the type-category recommendation list used for the EDHRec tab and
scoring, and (c) a normalized `name → {inclusion, synergy}` index built from **all**
cardlists. We then join that index onto the Slept On color-pool cards so they display
EDHRec's real inclusion %, and normalize the exclusion match so a card that is in the
EDHRec data can't leak into Slept On at `0%`.

## User Story
As a Brewer, I want Slept On cards to show their real inclusion % and to be scored
against ALL of my commander's card data, so that I can trust the data (not a
misleading 0%) and fringe-but-relevant cards aren't excluded just because they're off
a narrow default slice.

## Metadata
| Field | Value |
|-------|-------|
| Type | BUG_FIX + ENHANCEMENT |
| Complexity | MEDIUM |
| GitHub Issue | #15 |
| Systems Affected | `services/edhrec.py`, `services/analysis.py`, `app.py` (commander route) |

---

## Background / Spike Findings (verified against live EDHRec, 2026-06-20)

- Stable endpoint: `GET https://json.edhrec.com/pages/commanders/<slug>.json`
  (no Next.js `build_id`; same one `get_commander_info` already calls).
- `r["container"]["json_dict"]["card"]` → commander (`name`, `color_identity`,
  `image_uris[0].normal`). This is exactly today's `get_commander_info` source.
- `r["container"]["json_dict"]["cardlists"]` → list of 13 lists. Each list:
  `{ "header": "Creatures", "tag": "creatures", "cardviews": [ ... ] }`.
- Each **cardview**: keys `id, name, sanitized, url, inclusion, num_decks,
  potential_decks, synergy, trend_zscore`.
  - `edhrec_inclusion = inclusion / potential_decks` (e.g. `1107 / 7370 = 0.150`).
    This matches the current math in `get_commander_cards` (`inclusion` is the count).
  - `synergy` is a float already in `-1..1` range.
- Cardlist `tag` values: type categories =
  `creatures, instants, sorceries, utilityartifacts, manaartifacts, enchantments,
  planeswalkers, utilitylands, lands`; meta lists =
  `newcards, highsynergycards, topcards, gamechangers`.
- Atraxa main page: 13 lists, **292** total cardviews (deduped fewer). The meta lists
  are duplicates of cards already in the type categories.
- `total_card_count` / the root type-keyed ints (`creature`, `land`, …) are the
  **average-deck composition** (100-card deck), NOT a card universe — do not use them.
- `panels.taglinks` (183 entries) are the available themes — **out of scope here**
  (that powers issue #19's tag selector).

**Scoping decision:** the "full dataset" for #15 is the union of all cardlists from
the single main commander page. EDHRec does not expose an uncapped "every legal card"
inclusion list in one request (per-category pages just re-cap a different type and
rate-limit under rapid calls), so widening beyond the main page is deferred to the
tag/bracket work (#19). The inclusion **join is forward-compatible**: when #19 feeds a
larger index in, more Slept On cards light up automatically with no further change.

---

## Patterns to Follow

### Stable EDHRec page fetch (mirror exactly)
```python
# SOURCE: services/edhrec.py:16-34  (get_commander_info)
def get_commander_info(commander_name: str) -> dict | None:
    slug = slugify(commander_name)
    url = f"{EDHREC_JSON_BASE}/{slug}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        card = resp.json()["container"]["json_dict"]["card"]
        ...
    except Exception as e:
        logger.error("get_commander_info failed for %r: %s", commander_name, e)
        return None
```
- Reuse `EDHREC_JSON_BASE`, `HEADERS`, `slugify`, and the `logger`.
- Error contract (CLAUDE.md): catch, `logger.error(...)`, return `None`/empty — never
  raise into the route. The route already renders `error.html` on falsy data
  (`app.py:36-51`).

### Per-card scoring dict shape (preserve keys)
```python
# SOURCE: services/edhrec.py:50-61
seen[name] = {
    "name": name,
    "edhrec_category": category,
    "edhrec_synergy": float(card.get("synergy", 0.0)),
    "edhrec_inclusion": edhrec_inclusion,
    "otags": [], "type_line": "", "price_usd": None,
    "rarity": "", "image_uri": "", "buzzword_score": 0.0,
}
```

### Pure computation lives in analysis.py
```python
# SOURCE: services/analysis.py:154-184  (score_card / score_cards — no I/O)
def score_cards(color_pool, weights, edhrec_card_names):
    for card in color_pool:
        if card["name"] in edhrec_card_names:   # <-- exact-match exclusion to fix
            continue
        ...
```

### Route enrichment loop (mirror the join style)
```python
# SOURCE: app.py:56-57
for card in edhrec_cards:
    card.update(card_details.get(card["name"], scryfall._empty_card_details()))
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/analysis.py` | UPDATE | Add pure `normalize_name()`; make `score_cards` exclusion normalized. |
| `services/edhrec.py` | UPDATE | Fetch the page once; extract commander info, type-category cards, and an all-cardlists `inclusion_index`. Drop the fragile `pyedhrec` path. |
| `app.py` | UPDATE | Use the single-fetch data; build normalized exclusion set; join inclusion onto the color pool before scoring. |

No files are created. No new dependencies.

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Add a pure name-normalizer in analysis.py and use it for exclusion
- **File**: `services/analysis.py`
- **Action**: UPDATE
- **Implement**:
  1. Add a module-level pure function:
     ```python
     def normalize_name(name: str) -> str:
         """
         Canonical key for matching a card across EDHRec and Scryfall data:
         case-folded, front face only (split on " // "), surrounding whitespace
         stripped. Pure; used by both the EDHRec inclusion join and Slept On
         exclusion so a card present in the EDHRec data cannot also appear as a
         0%-inclusion Slept On pick.
         """
         return (name or "").split(" // ", 1)[0].strip().casefold()
     ```
     Mirror the front-face handling already used in `services/bulk.py:262-263`
     (`name.split(" // ", 1)[0]`).
  2. Change `score_cards` (`services/analysis.py:163-184`) to treat
     `edhrec_card_names` as a set of **already-normalized** names and compare with
     `normalize_name(card["name"])`:
     ```python
     def score_cards(color_pool, weights, edhrec_card_names):
         scored = []
         for card in color_pool:
             if normalize_name(card["name"]) in edhrec_card_names:
                 continue
             ...
     ```
     Update the docstring to say the exclusion set is normalized.
- **Mirror**: `services/bulk.py:262-263` (front-face split), `services/analysis.py:174-176`.
- **Validate**: `flake8 services/analysis.py && python -m py_compile services/analysis.py`

### Task 2: Single-fetch EDHRec page → commander info + cards + inclusion index
- **File**: `services/edhrec.py`
- **Action**: UPDATE
- **Implement**:
  1. Add `import analysis` access for `normalize_name`. Use a package-relative
     import consistent with the project: `from .analysis import normalize_name`
     (edhrec is an I/O service; analysis is pure — this direction is fine, no cycle
     since `analysis.py` imports nothing local).
  2. Add a constant for the meta (non-type) cardlist tags:
     ```python
     _META_TAGS = {"newcards", "highsynergycards", "topcards", "gamechangers"}
     ```
  3. Add `get_commander_data(slug)` — **one** HTTP GET to
     `f"{EDHREC_JSON_BASE}/{slug}.json"`, returning the parsed
     `resp.json()["container"]["json_dict"]` dict, or `None` on any error (mirror
     `get_commander_info`'s try/except + `logger.error`). It will be passed a slug
     (route already passes a slug); call `slugify(slug)` to stay idempotent.
  4. Add pure `commander_info_from_data(data)` returning the same shape
     `get_commander_info` returns today (`name`, `color_identity`, `image_uri`) from
     `data["card"]`. Guard missing keys; return `None` if `data`/`card` absent.
  5. Add pure `_card_from_cardview(cv, category)` that builds the scoring dict
     (Task "Patterns → per-card scoring dict shape"): compute
     `edhrec_inclusion = (cv.get("inclusion") or 0) / potential` where
     `potential = cv.get("potential_decks") or 0` (guard divide-by-zero → 0.0);
     `edhrec_synergy = float(cv.get("synergy") or 0.0)`.
  6. Add pure `cards_from_data(data)` returning the **type-category** recommendation
     list (skip lists whose `tag` is in `_META_TAGS`), deduped by `name` (first
     occurrence wins, as today), using each list's `header` as `edhrec_category`.
     This preserves today's EDHRec-tab grouping; the meta lists become #17's job.
  7. Add pure `inclusion_index_from_data(data)` returning
     `{ normalize_name(name): {"inclusion": float, "synergy": float} }` built from
     **all** cardlists (meta included), so the index is the broadest inclusion source
     the page offers. On duplicate names keep the first non-zero inclusion seen.
  8. Replace the body of `get_commander_cards(slug)` so it delegates to the new
     functions for backward-compatible callers:
     `data = get_commander_data(slug); return cards_from_data(data) if data else []`.
     Remove the `pyedhrec`/`EDHRec()` import and usage. (Leaving `requests` import.)
  9. Update `get_commander_info` to delegate too:
     `data = get_commander_data(name); return commander_info_from_data(data) if data else None`.
     Keep the public signature so the route change in Task 3 stays small.
- **Mirror**: `services/edhrec.py:16-65` (fetch + dict shape), `services/bulk.py:255-263`.
- **Validate**: `flake8 services/edhrec.py && python -m py_compile services/edhrec.py`

### Task 3: Wire single fetch + inclusion join into the commander route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  1. Fetch the page **once**: replace the separate `get_commander_info(slug)` +
     `get_commander_cards(slug)` calls (`app.py:36,46`) with:
     ```python
     data = edhrec.get_commander_data(slug)
     info = edhrec.commander_info_from_data(data) if data else None
     if not info:
         return render_template("error.html", message=f"Commander '{slug}' not found on EDHRec."), 404
     edhrec_cards = edhrec.cards_from_data(data)
     if not edhrec_cards:
         return render_template("error.html", message=f"No card data found for '{slug}'."), 404
     incl_index = edhrec.inclusion_index_from_data(data)
     ```
  2. Keep the Scryfall enrichment of `edhrec_cards` (`app.py:53-57`) unchanged.
  3. Build the color pool (`app.py:60`) unchanged, then **join EDHRec inclusion onto
     pool cards before scoring**, mirroring the existing enrichment-loop style:
     ```python
     for card in color_pool:
         hit = incl_index.get(analysis.normalize_name(card["name"]))
         if hit:
             card["edhrec_inclusion"] = hit["inclusion"]
             card["edhrec_synergy"] = hit["synergy"]
     ```
     Cards absent from the index keep their `0.0` default (the "no EDHRec data"
     sentinel — consistent with AC3).
  4. Build a **normalized** exclusion set for `score_cards`:
     ```python
     edhrec_names = {analysis.normalize_name(c["name"]) for c in edhrec_cards}
     edhrec_names.add(analysis.normalize_name(info["name"]))
     ```
     (Replaces the raw-name set at `app.py:65-66`.) Scoring/feature-weights still come
     from `edhrec_cards` (now the robust full type-category union) — satisfies AC4.
  5. Leave the `feature_stats`/`weights`/`score_cards`/render block otherwise intact.
     The Slept On template already renders `card.edhrec_inclusion` (`commander.html:40`)
     and `apply_inclusion_cap` (`services/analysis.py:187`) now has real values to act on.
- **Mirror**: `app.py:53-71` (existing route flow + enrichment loops).
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 4: Manual smoke test
- **File**: n/a (runtime verification)
- **Action**: verify
- **Implement**:
  1. `python app.py`, open `/commander/atraxa-praetors-voice`.
  2. EDHRec tab: categories render with data (parity with before).
  3. Slept On tab: cards now show **non-zero** inclusion % for cards EDHRec has data
     on; cards EDHRec lacks data on still show `0.0%`. Confirm no card appears in
     *both* the EDHRec tab and Slept On (normalized exclusion holds).
  4. Drag the "Inclusion cap" slider down and confirm high-inclusion cards drop out
     (the cap was previously a no-op because everything was 0%).
- **Validate**: visual; both sections populated, inclusion values present.

---

## Validation Sequence

```bash
# From repo root
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
# Manual smoke test
python app.py    # then load /commander/atraxa-praetors-voice
```

---

## Design Notes & Risks

| Risk | Mitigation |
|------|-----------|
| EDHRec card name ≠ Scryfall bulk name (DFC `//`, accents) so the join/exclusion misses | `normalize_name` (front-face + casefold) handles the common DFC/case cases; mirrors `bulk.py`'s front-face indexing. Names that still differ simply stay at the 0.0 sentinel — no crash, degrades gracefully. |
| Dropping `pyedhrec` changes which cards populate the EDHRec tab | The stable pages JSON returns the same `cardlists` pyedhrec parses, via a more reliable endpoint (no stale `build_id`). Net effect is equal-or-more cards. Smoke test (Task 4) confirms parity. |
| Meta lists (New/High/Top/Game Changers) duplicate type-category cards | `cards_from_data` skips `_META_TAGS` for the recommendation/scoring list (preserves today's grouping); they still feed `inclusion_index_from_data`. Their dedicated display is #17, not here. |
| Single fetch now feeds info + cards + index — one failure point | `get_commander_data` returns `None` on any error; route still renders `error.html` (unchanged contract). One fetch replaces today's two, so it's strictly fewer network calls. |
| `potential_decks` zero/missing on some cardviews | Guarded divide → `edhrec_inclusion = 0.0`. |
| `analysis` imported by `edhrec` | One-directional (`analysis` imports nothing local); no cycle. Keeps `normalize_name` defined once, pure, in the pure layer. |

---

## Acceptance Criteria

- [ ] `services/edhrec.py` fetches the commander's full cardlists from the stable
      `pages/commanders/<slug>.json` endpoint (all 13 lists), replacing the
      `pyedhrec` build-id path.
- [ ] A normalized `name → {inclusion, synergy}` index is joined onto Slept On color-
      pool cards so they display EDHRec's real inclusion %.
- [ ] Cards with no EDHRec data keep `edhrec_inclusion = 0.0` (sentinel) and render
      consistently.
- [ ] Default Slept On feature-weight scoring is built from the full type-category
      union (robust vs. the old narrow/fragile fetch).
- [ ] Normalized exclusion prevents any EDHRec-data card from also appearing in Slept
      On at 0%.
- [ ] `flake8 .` clean.
- [ ] `python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py` clean.
- [ ] Smoke test: `/commander/atraxa-praetors-voice` shows non-zero Slept On inclusion
      matching the EDHRec tab; the inclusion-cap slider now filters.
- [ ] Follows CLAUDE.md layering (fetch in `edhrec.py`, pure compute in `analysis.py`,
      route wiring in `app.py`) and the data-structure contract.
- [ ] GitHub Issue #15 criteria satisfied.
```
