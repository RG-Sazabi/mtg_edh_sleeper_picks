# Plan: Archidekt deck-URL input — parse, detect commander, route to analysis

## Summary
Add a second entry point on the landing page: an Archidekt deck URL. A new
`services/archidekt.py` parses the deck id from the URL, fetches the deck via Archidekt's
public JSON API, returns the detected commander(s) + the deck's card names, and the `/` POST
handler routes to the existing commander analysis view (`/commander/<slug>?deck=<id>`),
reusing `edhrec.slugify` / `resolve_pairing_slug`. Commander detection reads Archidekt's
command-zone category; a deck with no detectable commander (or an unreadable/invalid URL)
renders the existing friendly `error.html` rather than a 500. This issue stops at routing —
forcing inclusion = 100% for deck cards, the deck-scoped scoring, and the "in deck" badge are
issue #34, which re-fetches the deck by the `deck=<id>` query param.

## User Story
As a deckbuilder, I want to paste my Archidekt deck URL on the landing page, so that the app
can read my list and run a Slept On analysis for its commander.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | MEDIUM |
| GitHub Issue | #33 |
| Systems Affected | `services/archidekt.py` (new), `app.py` (index route), `templates/index.html` |
| Depends on | none (independent of the #31/#32 type-section track) |

---

## Archidekt API (verified against `https://archidekt.com/api/decks/1/`)
- `GET https://archidekt.com/api/decks/<id>/` → deck JSON. No key, anonymous.
- **Card name**: `cards[].card.oracleCard.name`.
- **Per-card categories**: `cards[].categories` — an array of category-name strings
  (e.g. `["Commander"]`).
- **Deck categories**: `categories[]` of `{ "name", "isPremier", "includedInDeck" }`.
  The command-zone category has `isPremier: true` (normally named `"Commander"`);
  maybeboard-style categories have `includedInDeck: false`.
- **Commander detection (robust):** premier names = `{c.name for c in deck.categories if
  c.isPremier}` (fallback `{"Commander"}` if none flagged); a card is a commander if its
  `categories` intersects that set.
- **Mainboard card names:** include a card unless *all* its `categories` are deck categories
  with `includedInDeck: false` (drops maybeboard/considering). Cards with no categories
  default to included.

---

## Patterns to Follow

### HTTP boundary service (mirror exactly: timeout, UA header, catch → None)
```python
# SOURCE: services/edhrec.py:7-8, 46-64 (_fetch_json_dict)
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}
def _fetch_json_dict(url: str) -> dict | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()...
    except Exception as e:
        logger.error("... failed for %r: %s", url, e)
        return None
```

### Slug + partner-pairing routing (reuse — do not reinvent)
```python
# SOURCE: services/edhrec.py:29-30 (slugify), 161-172 (resolve_pairing_slug)
# resolve_pairing_slug tries both orders and validates against EDHRec, returns a slug.
```

### Route → friendly error page (not a 500)
```python
# SOURCE: app.py:66-72 (commander route)
return (render_template("error.html", message="Commander '%s' not found..." % slug), 404)
```

### Index POST branch + redirect
```python
# SOURCE: app.py:16-29 (index)
if request.method == "POST":
    name = request.form.get("commander", "").strip()
    ...
    return redirect(url_for("commander", slug=slug))
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/archidekt.py` | CREATE | `parse_deck_id(url)`, `get_deck(deck_id)` → `{deck_id, commander_names, card_names}`; all Archidekt HTTP + URL parsing isolated here |
| `app.py` | UPDATE | Import `archidekt`; add the `archidekt_url` branch to the index POST; route to `/commander/<slug>?deck=<id>` or `error.html` |
| `templates/index.html` | UPDATE | Add a second input (Archidekt URL) + submit, in its own POST form |

No new dependencies (`requests` already used).

---

## Design Decisions

1. **`get_deck` takes a deck id, not a URL.** The issue sketch said `get_deck(url)`, but both
   callers ultimately hold an id: the index route parses the URL once; #34's commander route
   already has the id from the `deck=<id>` query param. So the seam is
   `parse_deck_id(url) -> str|None` + `get_deck(deck_id) -> dict|None`, which #34 reuses
   directly. (Minor, documented deviation from the issue's signature.)
2. **Untrusted-input safety.** `parse_deck_id` only accepts URLs whose host is
   `archidekt.com` (or `www.`) and extracts `\d+` after `/decks/`; anything else → `None`.
   The numeric id is interpolated into the API path, never the raw URL.
3. **Commander count:** 1 → single (`slugify`); 2 → partner pairing (`resolve_pairing_slug`);
   0 → friendly error; >2 → friendly error (ambiguous command zone — rare, defer).
4. **Routing carries `deck=<id>`** even though nothing consumes it yet, establishing the
   contract #34 builds on. With #33 only, the commander route ignores the param and renders a
   normal (commander-average) analysis — a useful intermediate state.
5. **Two POST forms on the landing page**, both to `/`. The route checks `archidekt_url`
   first, else falls through to the existing commander/partner logic. Keeps the commander
   autocomplete/auto-submit flow untouched.

---

## Tasks

### Task 1: Create `services/archidekt.py`
- **File**: `services/archidekt.py`
- **Action**: CREATE
- **Implement**:
  - Module docstring noting the layer rule (all Archidekt HTTP + URL parsing live here;
    callers get plain dicts/`None`). `import logging`, `import re`, `import requests`;
    `logger = logging.getLogger(__name__)`; `HEADERS` + `API_BASE =
    "https://archidekt.com/api/decks"`.
  - `parse_deck_id(url: str) -> str | None`: return the deck id if `url` is an
    `archidekt.com` deck URL (`re.search(r"archidekt\.com/(?:api/)?decks/(\d+)", url)` after a
    host check), else `None`. Strip whitespace; tolerate trailing slug/query/hash.
  - `_fetch(deck_id: str) -> dict | None`: GET `f"{API_BASE}/{deck_id}/"` with `HEADERS`,
    `timeout=10`, `raise_for_status`, return `resp.json()`; catch `Exception` → `logger.error`
    + `None`. Mirror `edhrec._fetch_json_dict`.
  - `_commander_names(deck: dict) -> list[str]`: premier set from
    `deck.get("categories", [])` where `c.get("isPremier")`; fallback `{"Commander"}`. Return
    `[card["card"]["oracleCard"]["name"] for card in deck.get("cards", []) if
    set(card.get("categories") or []) & premier]`, de-duped, order-preserving. Guard missing
    nested keys.
  - `_card_names(deck: dict) -> list[str]`: included-category names =
    `{c["name"] for c in deck.get("categories", []) if c.get("includedInDeck", True)}`;
    include a card unless it has categories and none are in the included set; map to
    `card.oracleCard.name`; de-dupe, order-preserving.
  - `get_deck(deck_id: str) -> dict | None`: `deck = _fetch(deck_id)`; if `None` return
    `None`; else return `{"deck_id": deck_id, "commander_names": _commander_names(deck),
    "card_names": _card_names(deck)}`. Never raises.
- **Mirror**: `services/edhrec.py:46-64` (fetch), `:7-10` (HEADERS/logger).
- **Validate**: `flake8 services/archidekt.py && python -m py_compile services/archidekt.py`

### Task 2: Wire the Archidekt branch into the index route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement**:
  - Add `archidekt` to the services import (line 5).
  - At the top of the `if request.method == "POST":` block (line 18), before the commander
    read, handle the deck URL:
    ```python
    archidekt_url = request.form.get("archidekt_url", "").strip()
    if archidekt_url:
        deck_id = archidekt.parse_deck_id(archidekt_url)
        deck = archidekt.get_deck(deck_id) if deck_id else None
        if not deck:
            return render_template(
                "error.html",
                message="Couldn't read that Archidekt deck. Check the URL is a public "
                        "archidekt.com deck link.",
            ), 400
        names = deck["commander_names"]
        if not names or len(names) > 2:
            return render_template(
                "error.html",
                message="Couldn't find a commander in that deck. The deck needs a card in "
                        "its Commander category.",
            ), 400
        if len(names) == 2:
            slug = edhrec.resolve_pairing_slug(names[0], names[1])
        else:
            slug = edhrec.slugify(names[0])
        return redirect(url_for("commander", slug=slug, deck=deck["deck_id"]))
    ```
  - Leave the existing commander/partner logic untouched below this branch.
- **Mirror**: `app.py:16-29` (index POST) and the error-render pattern at `app.py:66-72`.
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 3: Add the Archidekt input to the landing page
- **File**: `templates/index.html`
- **Action**: UPDATE
- **Implement**: Below the existing commander `<form>` (after line 25's hint paragraph), add
  a divider and a second POST form:
  ```html
  <p class="or-divider">— or —</p>
  <form method="POST" action="{{ url_for('index') }}" class="archidekt-form">
    <input type="url" name="archidekt_url" id="archidekt-input"
           placeholder="Paste an Archidekt deck URL…" autocomplete="off">
    <button type="submit">Analyze deck</button>
  </form>
  ```
  No autocomplete JS needed (plain URL field). Optionally add light CSS for `.or-divider`
  in `static/css/style.css` (centered, muted) — minor; skip if time-boxed since unstyled is
  functional.
- **Mirror**: existing form markup at `templates/index.html:6-22`.
- **Validate**: smoke test (Task 4).

### Task 4: Validate + manual smoke test
- **File**: — (verification only)
- **Action**: VALIDATE
- **Implement**: Run the validation sequence, then `python app.py` and on the landing page:
  - Paste a real public deck, e.g. `https://archidekt.com/decks/1/` (commander
    "Thelon of Havenwood") → redirects to that commander's analysis page; URL carries
    `?deck=1`.
  - Paste a non-Archidekt URL (e.g. `https://example.com/x`) → friendly error, no 500.
  - Paste an Archidekt URL for a deck with no Commander category → "Couldn't find a
    commander…" error.
  - Confirm the existing commander-name search still works (no regression).
- **Validate**: see Validation Sequence.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/archidekt.py
# Manual smoke (per CLAUDE.md): python app.py
#   - Archidekt URL https://archidekt.com/decks/1/  -> Thelon of Havenwood analysis, ?deck=1
#   - bad URL -> error.html ; commander search -> still works
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Archidekt blocks default `requests` UA / rate-limits | Send the project `User-Agent`; `timeout=10`; catch → `None` → friendly error. Isolated in `archidekt.py`. |
| Command-zone category not literally named "Commander" (custom premier name) | Detect via the `isPremier` flag on deck categories, not the literal string; fallback to `{"Commander"}`. |
| Partner/background decks have 2 command-zone cards | `len == 2` → `resolve_pairing_slug` (existing, validates ordering against EDHRec). |
| Detected commander absent from EDHRec | Routing still redirects; the commander route's existing 404/error path handles it. Not #33's concern. |
| Archidekt API shape changes | All field access guarded + isolated in `archidekt.py`; failures degrade to the friendly error (mirror the pyedhrec-breakage note in CLAUDE.md). |
| Untrusted URL injection | `parse_deck_id` host-checks + extracts only `\d+`; only the numeric id hits the API path. |

---

## Acceptance Criteria

- [ ] All tasks completed
- [ ] `flake8 .` clean; `python -m py_compile app.py services/archidekt.py` clean
- [ ] No test suite (per CLAUDE.md) — manual smoke test passes
- [ ] GitHub Issue #33 criteria satisfied:
  - [ ] Landing page has a second input accepting an Archidekt deck URL
  - [ ] `services/archidekt.py` exposes `parse_deck_id` + `get_deck` (id-based; documented deviation)
  - [ ] Deck fetched via the public API with timeout + UA, errors caught → `None`
  - [ ] Commander detected via the Commander/premier category; 2 commanders → partner pairing
  - [ ] No commander / fetch failure / non-Archidekt URL → friendly `error.html`, not a 500
  - [ ] Valid input redirects to `/commander/<slug>?deck=<id>`
  - [ ] Existing commander-name flow unaffected

---

## Out of Scope (deferred to #34)
- Forcing inclusion = 100% for deck cards, deck-scoped scoring, the "in deck" badge
- Maybeboard/companion/category semantics beyond commander detection + mainboard names
- User-driven commander selection when detection is ambiguous (MVP errors)
- Caching fetched decks; deck sources other than Archidekt
