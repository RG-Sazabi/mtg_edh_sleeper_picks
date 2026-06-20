# Plan: Issue #2 — Buzzword Score Engine (analysis.py)

## Summary
Create `services/analysis.py` with three pure functions. `compute_tf` builds a term-frequency dict from the EDHRec card list, weighting each otag by the card's `edhrec_synergy`. `score_cards` uses that TF dict to assign a `buzzword_score` to every color-pool card not already in the EDHRec set. `apply_inclusion_cap` filters out Slept On cards whose EDHRec inclusion rate exceeds a threshold. No I/O, no imports of Flask or requests — pure in, pure out.

## User Story
As a deckbuilder, I want the app to compute a Buzzword Score for every card in the commander's color identity, so that underplayed cards with high functional overlap with the EDHRec list rise to the top.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | LOW |
| GitHub Issue | #2 |
| Systems Affected | services/analysis.py (new file only) |

---

## Confirmed Data Shapes (from reading existing services)

### EDHRec card (input to `compute_tf`)
```python
{
    "name": str,
    "edhrec_category": str,
    "edhrec_synergy": float,    # 0.0–~0.5, already a fraction
    "edhrec_inclusion": float,  # 0.0–1.0 (inclusion/potential_decks)
    "otags": list[str],         # populated after scryfall.get_card_details()
    "price_usd": float | None,
    "rarity": str,
    "image_uri": str,
    "buzzword_score": float,    # 0.0, to be filled by score_cards
}
```

### Color-pool card (input to `score_cards`)
Same shape, but `edhrec_synergy=0.0`, `edhrec_inclusion=0.0`, `edhrec_category=""`.

---

## Algorithm

```
# compute_tf
TF: dict[str, float] = {}
for card in edhrec_cards:
    weight = card["edhrec_synergy"]   # use edhrec_inclusion as fallback if synergy == 0.0
    for tag in card["otags"]:
        TF[tag] = TF.get(tag, 0.0) + weight

# score_cards
for card in color_pool:
    if card["name"] in edhrec_card_names:
        continue                       # skip cards already in the EDHRec list
    score = sum(TF.get(tag, 0.0) for tag in card["otags"])
    card["buzzword_score"] = score

return sorted(
    [c for c in color_pool if c["name"] not in edhrec_card_names and c["buzzword_score"] > 0],
    key=lambda c: c["buzzword_score"],
    reverse=True
)

# apply_inclusion_cap
return [c for c in slept_on if c["edhrec_inclusion"] <= cap]
```

**Fallback rule**: In `compute_tf`, if `edhrec_synergy == 0.0`, use `edhrec_inclusion` as the weight instead. This handles the case where PyEDHRec returns zero synergy for some cards (e.g. staples with no unique commander synergy). Document with a comment.

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/analysis.py` | CREATE | Three pure scoring functions |

---

## Tasks

### Task 1: Create services/analysis.py

- **File**: `services/analysis.py`
- **Action**: CREATE
- **Implement**:

```python
import logging

logger = logging.getLogger(__name__)


def compute_tf(edhrec_cards: list[dict]) -> dict[str, float]:
    """
    Build a term-frequency dict: otag -> sum of synergy weights across all EDHRec cards.
    Falls back to edhrec_inclusion as weight when edhrec_synergy is 0.0.
    """
    tf: dict[str, float] = {}
    for card in edhrec_cards:
        weight = card.get("edhrec_synergy") or card.get("edhrec_inclusion", 0.0)
        for tag in card.get("otags", []):
            tf[tag] = tf.get(tag, 0.0) + weight
    return tf


def score_cards(
    color_pool: list[dict],
    tf: dict[str, float],
    edhrec_card_names: set[str],
) -> list[dict]:
    """
    Assign buzzword_score to each color-pool card not already in edhrec_card_names.
    Returns list sorted descending by buzzword_score, excluding zero-score cards.
    """
    scored = []
    for card in color_pool:
        if card["name"] in edhrec_card_names:
            continue
        score = sum(tf.get(tag, 0.0) for tag in card.get("otags", []))
        if score > 0:
            card = dict(card)  # don't mutate the input
            card["buzzword_score"] = score
            scored.append(card)
    scored.sort(key=lambda c: c["buzzword_score"], reverse=True)
    return scored


def apply_inclusion_cap(slept_on: list[dict], cap: float) -> list[dict]:
    """
    Filter out cards whose edhrec_inclusion exceeds cap.
    Note: color-pool cards have edhrec_inclusion=0.0 by default (they are not in
    the EDHRec list), so this filter primarily catches borderline cross-reference cases.
    """
    return [c for c in slept_on if c.get("edhrec_inclusion", 0.0) <= cap]
```

- **Validate**: `"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -m py_compile services/analysis.py`

---

### Task 2: Lint check

- **Action**: VALIDATE
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" services/analysis.py --max-line-length=119
  ```
- Fix all errors before continuing.

---

### Task 3: Unit correctness check (no network required)

- **Action**: VALIDATE — run this inline test to verify logic without any API calls
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -c "
  from services.analysis import compute_tf, score_cards, apply_inclusion_cap

  # Minimal fixture data
  edhrec_cards = [
      {'name': 'Sol Ring',    'edhrec_synergy': 0.05, 'edhrec_inclusion': 0.99, 'otags': ['ramp', 'mana']},
      {'name': 'Arcane Signet','edhrec_synergy': 0.03, 'edhrec_inclusion': 0.90, 'otags': ['ramp', 'color-fix']},
      {'name': 'Swords',      'edhrec_synergy': 0.08, 'edhrec_inclusion': 0.70, 'otags': ['removal', 'exile']},
  ]
  edhrec_names = {c['name'] for c in edhrec_cards}

  color_pool = [
      {'name': 'Everflowing Chalice', 'edhrec_synergy': 0.0, 'edhrec_inclusion': 0.0, 'otags': ['ramp', 'mana'],    'buzzword_score': 0.0},
      {'name': 'Skullclamp',          'edhrec_synergy': 0.0, 'edhrec_inclusion': 0.0, 'otags': ['removal'],          'buzzword_score': 0.0},
      {'name': 'Exotic Orchard',      'edhrec_synergy': 0.0, 'edhrec_inclusion': 0.05,'otags': ['ramp', 'color-fix'],'buzzword_score': 0.0},
      {'name': 'Sol Ring',            'edhrec_synergy': 0.0, 'edhrec_inclusion': 0.99,'otags': ['ramp', 'mana'],     'buzzword_score': 0.0},  # should be excluded
  ]

  tf = compute_tf(edhrec_cards)
  print('TF:', tf)
  assert tf['ramp'] == pytest_approx(0.08) if False else abs(tf['ramp'] - 0.08) < 0.0001, f'ramp TF wrong: {tf[\"ramp\"]}'
  assert 'removal' in tf
  assert 'mana' in tf

  slept_on = score_cards(color_pool, tf, edhrec_names)
  print('Slept On:', [(c['name'], round(c['buzzword_score'], 3)) for c in slept_on])
  assert all(c['name'] != 'Sol Ring' for c in slept_on), 'Sol Ring must be excluded'
  assert slept_on[0]['buzzword_score'] >= slept_on[-1]['buzzword_score'], 'Not sorted desc'
  assert all(c['buzzword_score'] > 0 for c in slept_on), 'Zero-score cards must be excluded'

  capped = apply_inclusion_cap(slept_on, cap=0.04)
  names_after_cap = [c['name'] for c in capped]
  print('After cap:', names_after_cap)
  assert 'Exotic Orchard' not in names_after_cap, 'Exotic Orchard (5% inclusion) should be excluded at 4% cap'

  print('ALL ASSERTIONS PASSED')
  "
  ```
- Expected output ends with `ALL ASSERTIONS PASSED`.

---

### Task 4: End-to-end CLI smoke test (requires network)

- **Action**: VALIDATE — confirms real EDHRec + Scryfall data flows through analysis correctly
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -c "
  import logging
  logging.basicConfig(level=logging.WARNING)

  from services.scryfall import _load_otag_index, get_card_details, get_color_identity_pool
  from services.edhrec import get_commander_cards, get_commander_info
  from services.analysis import compute_tf, score_cards, apply_inclusion_cap

  print('Loading oracle tag index (one-time, ~17MB download)...')
  _load_otag_index()
  print('Done.')

  print('Fetching EDHRec cards for Atraxa...')
  cards = get_commander_cards('Atraxa, Praetors Voice')
  print(f'  {len(cards)} EDHRec cards')

  print('Enriching first 20 cards with Scryfall data...')
  for card in cards[:20]:
      details = get_card_details(card['name'])
      card.update(details)
  tagged = sum(1 for c in cards[:20] if c['otags'])
  print(f'  {tagged}/20 cards have otags')

  tf = compute_tf(cards[:20])
  print(f'TF dict has {len(tf)} unique otags')
  top_tags = sorted(tf.items(), key=lambda x: x[1], reverse=True)[:5]
  print(f'Top 5 tags: {top_tags}')

  # Small color pool test (just 1 page of results to keep it fast)
  print('Fetching 1 page of color pool...')
  from services import scryfall
  import requests, time
  resp = requests.get('https://api.scryfall.com/cards/search',
      params={'q': 'id<=BGUW f:edh', 'order': 'edhrec'},
      headers=scryfall.HEADERS)
  time.sleep(0.1)
  pool_page = []
  if resp.status_code == 200:
      for c in resp.json().get('data', []):
          oid = c.get('oracle_id', '')
          pool_page.append({
              'name': c['name'], 'oracle_id': oid,
              'edhrec_synergy': 0.0, 'edhrec_inclusion': 0.0,
              'otags': scryfall._otag_index.get(oid, []),
              'price_usd': None, 'rarity': c.get('rarity',''),
              'image_uri': '', 'buzzword_score': 0.0,
          })

  edhrec_names = {c['name'] for c in cards[:20]}
  slept_on = score_cards(pool_page, tf, edhrec_names)
  print(f'Slept On cards (from 1-page sample): {len(slept_on)}')
  for c in slept_on[:5]:
      print(f'  {c[\"name\"]}: score={c[\"buzzword_score\"]:.3f}  otags={c[\"otags\"][:3]}')

  assert all(c['name'] not in edhrec_names for c in slept_on), 'EDHRec card appeared in Slept On!'
  assert all(c['buzzword_score'] > 0 for c in slept_on), 'Zero-score card in results!'
  if len(slept_on) > 1:
      assert slept_on[0]['buzzword_score'] >= slept_on[1]['buzzword_score'], 'Not sorted!'
  print('END-TO-END SMOKE TEST PASSED')
  "
  ```
- Expected: Top 5 Slept On cards printed with non-zero scores, `END-TO-END SMOKE TEST PASSED`.

---

## Validation Sequence

```bash
# 1. Compile
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -m py_compile services/analysis.py

# 2. Lint
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" services/analysis.py --max-line-length=119

# 3. Unit test (no network)
# (Task 3 command above)

# 4. End-to-end (network required, takes ~30s)
# (Task 4 command above)
```

---

## Acceptance Criteria

- [ ] `services/analysis.py` exists with `compute_tf`, `score_cards`, `apply_inclusion_cap`
- [ ] No imports of `flask`, `requests`, or any service module — pure functions only
- [ ] `compute_tf` fallback: uses `edhrec_inclusion` when `edhrec_synergy == 0.0`, documented in comment
- [ ] `score_cards` never returns a card whose name is in `edhrec_card_names`
- [ ] `score_cards` never returns a card with `buzzword_score == 0`
- [ ] `score_cards` result is sorted descending by `buzzword_score`
- [ ] `score_cards` does NOT mutate input dicts (uses `dict(card)` copy before assigning score)
- [ ] `apply_inclusion_cap` limitation documented in comment (color-pool cards default to 0.0)
- [ ] Unit correctness check (Task 3) passes all assertions
- [ ] `flake8 services/analysis.py --max-line-length=119` passes with zero errors
- [ ] Resolves GitHub Issue #2
