# Plan: Issue #1 — EDHRec and Scryfall Data Pipeline

## Summary
Create `requirements.txt`, `services/__init__.py`, `services/edhrec.py`, and `services/scryfall.py`. The edhrec service wraps PyEDHRec and flattens its category-keyed dict into a list of card dicts. The scryfall service downloads the oracle_tags bulk file once at startup to build an in-memory `oracle_id → [tag_slugs]` index, then fetches individual card data (price, rarity, image_uri, oracle_id) via the `/cards/named` endpoint. A separate `get_color_identity_pool()` function paginates the Scryfall card search for all EDH-legal cards within the commander's color identity.

## User Story
As a deckbuilder, I want the app to fetch EDHRec card data and enrich each card with Scryfall oracle tags, prices, and rarity, so that downstream analysis has all the data it needs.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | MEDIUM |
| GitHub Issue | #1 |
| Systems Affected | services/edhrec.py, services/scryfall.py, requirements.txt |

---

## Key API Facts (verified by live inspection)

### PyEDHRec
- Instantiate: `EDHRec()` (no args needed)
- `edhrec.get_commander_cards("atraxa praetors voice")` returns `dict[str, list[dict]]`
  - Keys are category headers: `"New Cards"`, `"High Synergy Cards"`, `"Creatures"`, etc.
  - Each card dict: `{id, name, sanitized, url, synergy: float, inclusion: int, num_decks: int, potential_decks: int, trend_zscore}`
  - `inclusion` = raw deck count (e.g. 1096). `potential_decks` = total decks that could run it.
  - **Compute fraction**: `edhrec_inclusion = inclusion / potential_decks`
- Commander `color_identity` comes from: `GET https://json.edhrec.com/pages/commanders/{slug}.json` → `container.json_dict.card.color_identity` (list of single-letter strings like `["G","W","U","B"]`)
- `EDHRec.format_card_name(name)` → slugifies (lowercase, spaces→hyphens, strip `'` and `,`)

### Scryfall
- All requests need header: `User-Agent: mtg-edh-sleeper-picks/1.0 (personal project)`
- Single card: `GET https://api.scryfall.com/cards/named?exact={name}` → card object with `oracle_id`, `prices.usd`, `rarity`, `image_uris.normal`, `set`, `collector_number`
- Oracle tags: **NOT available per-card via API**. Must use bulk data:
  - `GET https://api.scryfall.com/bulk-data` → find entry with `type == "oracle_tags"` → get `download_uri`
  - Download that URI → array of `{slug: str, taggings: [{oracle_id: str, weight: str}]}`
  - Invert into `dict[oracle_id, list[slug]]`
  - Cache this dict in module-level variable; refresh only if file is >24h old or on cold start
- Color identity pool: `GET https://api.scryfall.com/cards/search?q=id<={COLORSTRING}+f:edh&order=edhrec`
  - COLORSTRING example: `GWUB` (concatenate color letters)
  - Paginate: response has `has_more` bool and `next_page` URL
  - Sleep 0.1s between page requests
- Rate limit: max 10 req/sec — always sleep 0.1s between card-level requests

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `requirements.txt` | CREATE | Pin all dependencies |
| `services/__init__.py` | CREATE | Package marker |
| `services/edhrec.py` | CREATE | PyEDHRec wrapper — returns flat list of card dicts |
| `services/scryfall.py` | CREATE | Scryfall REST calls — oracle_tags bulk index + per-card details + color pool |

---

## Tasks

### Task 1: Create requirements.txt
- **File**: `requirements.txt`
- **Action**: CREATE
- **Implement**:
  ```
  flask>=3.0
  pyedhrec==0.0.2
  requests>=2.31
  frozen-flask>=1.0
  flake8>=7.0
  black>=26.0
  ```
- **Validate**: `"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/pip" install -r requirements.txt` — all already installed, should say "already satisfied"

---

### Task 2: Create services/__init__.py
- **File**: `services/__init__.py`
- **Action**: CREATE
- **Implement**: Empty file (package marker only)
- **Validate**: `"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -c "import services"`

---

### Task 3: Create services/edhrec.py
- **File**: `services/edhrec.py`
- **Action**: CREATE
- **Implement** the following functions:

**`slugify(name: str) -> str`**
- Replicate `EDHRec.format_card_name`: lowercase, spaces→hyphens, strip `'` and `,`
- Example: `"Atraxa, Praetors' Voice"` → `"atraxa-praetors-voice"`

**`get_commander_info(commander_name: str) -> dict | None`**
- Hit `https://json.edhrec.com/pages/commanders/{slug}.json` with `requests.get`
- Extract `response.json()["container"]["json_dict"]["card"]`
- Return `{"name": card["name"], "color_identity": card["color_identity"], "image_uri": card["image_uris"][0]["normal"]}` or `None` on any error
- Use `requests` directly (not PyEDHRec) since PyEDHRec doesn't expose this cleanly
- Add `User-Agent` header

**`get_commander_cards(commander_name: str) -> list[dict]`**
- Instantiate `EDHRec()`, call `.get_commander_cards(commander_name)`
- Returns `dict[header, list[cardview]]`
- Flatten into `list[dict]` with one entry per card, adding `edhrec_category = header`
- Compute `edhrec_inclusion = card["inclusion"] / card["potential_decks"]` (guard div-by-zero → 0.0)
- Keep `edhrec_synergy = card["synergy"]` as-is (already a float)
- Initialize fields that scryfall will fill: `otags=[]`, `price_usd=None`, `rarity=""`, `image_uri=""`, `buzzword_score=0.0`
- Deduplicate by card name (same card can appear in multiple categories — keep first occurrence, preserve category of first)
- Wrap everything in try/except; log errors with `logging.getLogger(__name__).error(...)`; return `[]` on failure

Full card dict shape returned:
```python
{
    "name": str,
    "edhrec_category": str,
    "edhrec_synergy": float,   # e.g. 0.063
    "edhrec_inclusion": float, # e.g. 0.15 (fraction, 0–1)
    "otags": [],               # filled by scryfall
    "price_usd": None,         # filled by scryfall
    "rarity": "",              # filled by scryfall
    "image_uri": "",           # filled by scryfall
    "buzzword_score": 0.0,     # filled by analysis
}
```

**Validate**:
```bash
.venv/Scripts/python -c "
from services.edhrec import get_commander_cards, get_commander_info
cards = get_commander_cards('Atraxa, Praetors Voice')
print(len(cards), 'cards')
print(cards[0])
info = get_commander_info('Atraxa, Praetors Voice')
print(info)
"
```
Expected: ≥100 cards, info shows `color_identity: ['G', 'W', 'U', 'B']`

---

### Task 4: Create services/scryfall.py
- **File**: `services/scryfall.py`
- **Action**: CREATE

**Module-level constants and cache**:
```python
import logging
import time
import requests

SCRYFALL_BASE = "https://api.scryfall.com"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}
_card_cache: dict = {}          # name -> card details dict
_otag_index: dict = {}          # oracle_id -> list[tag_slug]
_otag_index_loaded = False

logger = logging.getLogger(__name__)
```

**`_load_otag_index() -> None`** (call once, lazy)
- If `_otag_index_loaded` is True, return immediately
- `GET https://api.scryfall.com/bulk-data` with HEADERS
- Find entry where `item["type"] == "oracle_tags"`, get `download_uri`
- `GET download_uri` (streaming ok) — parse JSON array
- For each tag object, for each tagging in `tag["taggings"]`: `_otag_index[tagging["oracle_id"]].append(tag["slug"])`
- Use `collections.defaultdict(list)` then convert to plain dict
- Set `_otag_index_loaded = True`
- Wrap in try/except; log error if fails (otags will just be empty)

**`_get(url: str, params: dict = None) -> dict | None`** (private)
- `requests.get(url, params=params, headers=HEADERS)`
- Sleep 0.1s after the request
- Return `.json()` if status 200, else log error and return `None`

**`get_card_details(name: str) -> dict`**
- Check `_card_cache` first; return cached result if present
- Call `_get(f"{SCRYFALL_BASE}/cards/named", {"exact": name})`
- If None or response has `"error"` key, return empty details dict: `{"otags": [], "price_usd": None, "rarity": "", "image_uri": ""}`
- Extract:
  - `oracle_id = card["oracle_id"]`
  - `price_usd = float(card["prices"]["usd"]) if card["prices"].get("usd") else None`
  - `rarity = card["rarity"]`
  - `image_uri = card.get("image_uris", {}).get("normal", "")` — note: double-faced cards have no top-level `image_uris`; fall back to `card.get("card_faces", [{}])[0].get("image_uris", {}).get("normal", "")`
- Ensure `_load_otag_index()` has been called
- `otags = _otag_index.get(oracle_id, [])`
- Build result dict, store in `_card_cache[name]`, return it

**`get_color_identity_pool(color_identity: list[str]) -> list[dict]`**
- Build color string: `"".join(sorted(color_identity))` (e.g. `"BGUW"`)
- Query: `q = f"id<={color_string}+f:edh"` (Scryfall will filter to EDH-legal cards in that color identity)
- Paginate: start with `GET {SCRYFALL_BASE}/cards/search?q={q}&order=edhrec`
- Each page: extract `data` list, check `has_more`, follow `next_page` URL
- For each card in results, build a minimal dict:
  ```python
  {
      "name": card["name"],
      "oracle_id": card.get("oracle_id", ""),
      "edhrec_category": "",
      "edhrec_synergy": 0.0,
      "edhrec_inclusion": 0.0,
      "otags": _otag_index.get(card.get("oracle_id", ""), []),
      "price_usd": float(card["prices"]["usd"]) if card.get("prices", {}).get("usd") else None,
      "rarity": card.get("rarity", ""),
      "image_uri": card.get("image_uris", {}).get("normal", "") or (card.get("card_faces") or [{}])[0].get("image_uris", {}).get("normal", ""),
      "buzzword_score": 0.0,
  }
  ```
- Ensure `_load_otag_index()` is called before starting pagination
- Return flat list of all pages combined
- Wrap in try/except; return `[]` on failure

**Validate**:
```bash
.venv/Scripts/python -c "
from services.scryfall import get_card_details, get_color_identity_pool, _load_otag_index
_load_otag_index()
d = get_card_details('Sol Ring')
print('Sol Ring:', d)
pool = get_color_identity_pool(['W','U','B','G'])
print('pool size:', len(pool))
print('sample:', pool[0])
"
```
Expected: Sol Ring has price, rarity="uncommon", some otags; pool has thousands of cards.

---

### Task 5: Lint check
- **Action**: VALIDATE
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" services/
  ```
- Fix all errors before marking done. Common issues: line length (E501 — max 119 chars is fine for personal project, add `--max-line-length=119`), unused imports.

---

### Task 6: Full smoke test
- **Action**: VALIDATE
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -c "
  from services.edhrec import get_commander_cards, get_commander_info
  from services.scryfall import get_card_details, _load_otag_index

  print('Loading otag index...')
  _load_otag_index()
  print('Done.')

  info = get_commander_info('Atraxa, Praetors Voice')
  print('Commander:', info)

  cards = get_commander_cards('Atraxa, Praetors Voice')
  print(f'{len(cards)} EDHRec cards')

  # Enrich first 3 cards
  for card in cards[:3]:
      details = get_card_details(card['name'])
      card.update(details)
      print(f'  {card[\"name\"]}: price={card[\"price_usd\"]}, rarity={card[\"rarity\"]}, otags={card[\"otags\"][:3]}')
  "
  ```
- Expected: ≥100 cards, first 3 show price, rarity, and at least some otags.

---

## Validation Sequence

```bash
# 1. Lint
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" services/ --max-line-length=119

# 2. Compile check
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -m py_compile services/edhrec.py services/scryfall.py

# 3. Smoke test (Task 6 above)
```

---

## Acceptance Criteria

- [ ] `requirements.txt` exists with all 6 packages
- [ ] `services/__init__.py` exists
- [ ] `get_commander_cards("Atraxa, Praetors Voice")` returns ≥100 card dicts with correct fields
- [ ] `get_commander_info("Atraxa, Praetors Voice")` returns `color_identity: ["G","W","U","B"]`
- [ ] `get_card_details("Sol Ring")` returns `rarity="uncommon"`, numeric `price_usd`, non-empty `image_uri`
- [ ] `get_card_details("Sol Ring")["otags"]` is a list (may be empty if oracle_id not in index, but not an error)
- [ ] `_load_otag_index()` populates `_otag_index` with >1000 keys
- [ ] `get_color_identity_pool(["W","U","B","G"])` returns a list with >1000 cards
- [ ] No bare `print()` in services/ — use `logging`
- [ ] `flake8 services/ --max-line-length=119` passes with zero errors
- [ ] Resolves GitHub Issue #1
