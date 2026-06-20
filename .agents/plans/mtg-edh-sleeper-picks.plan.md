# Plan: MTG EDH Sleeper Picks — Full Application

## Summary
Build a Flask + Jinja2 web app that fetches EDHRec commander data via PyEDHRec, enriches each card with Scryfall oracle tags (otags) and prices, runs a weighted term-frequency analysis to produce a "Buzzword Score" for underplayed cards, and renders two sections: the standard EDHRec card list and a "Slept On" section of high-scoring hidden gems. Client-side JS handles all filter interactions (price cap, pauper toggle, N slider, inclusion cap) without page reloads. A separate `export.py` renders static HTML to `/docs` for optional GitHub Pages hosting.

## User Story
As a Commander deckbuilder, I want to search for any legal commander and see both the standard EDHRec recommendations and a scored list of underplayed cards that share functional DNA with those recommendations, so that I can find non-obvious includes my opponents won't expect.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | HIGH |
| GitHub Issue | N/A |
| Systems Affected | Data pipeline, scoring engine, Flask routes, Jinja2 templates, client-side filters, static export |

---

## Patterns to Follow

### Project conventions (from CLAUDE.md)
- Files: `snake_case.py` for Python, `kebab-case` for static assets
- Variables / functions: `snake_case`
- Constants: `SCREAMING_SNAKE_CASE`
- Routes call services only — no API calls inside `app.py`
- Services return plain `dict` / `list` — no Flask objects
- `analysis.py` is pure functions — no I/O, no imports from `flask` or `requests`

### Error handling
- Scryfall and PyEDHRec calls catch HTTP/library errors and return `None` or `[]`
- Routes check for `None` and render an error template rather than raising 500
- Use `app.logger.error(...)` — no bare `print()` in service or route code

### Scryfall rate limiting
- 0.1s sleep between card-level requests (`time.sleep(0.1)`)
- Module-level dict cache keyed by card name, scoped to the process lifetime

### Card data shape (canonical dict)
```python
{
  "name": str,
  "edhrec_synergy": float,      # 0.0–1.0 from PyEDHRec
  "edhrec_inclusion": float,    # 0.0–1.0 fraction of decks
  "edhrec_category": str,       # e.g. "Ramp", "Card Draw"
  "otags": list[str],           # e.g. ["ramp", "draw"]
  "price_usd": float | None,    # Scryfall prices.usd
  "rarity": str,                # "common" | "uncommon" | "rare" | "mythic"
  "image_uri": str,             # Scryfall normal image URL
  "buzzword_score": float,      # 0.0 for EDHRec cards; computed for Slept On
}
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `requirements.txt` | CREATE | Pin all dependencies |
| `app.py` | CREATE | Flask app, two routes: `/` and `/commander/<slug>` |
| `services/__init__.py` | CREATE | Empty package marker |
| `services/edhrec.py` | CREATE | PyEDHRec calls → list of card dicts |
| `services/scryfall.py` | CREATE | Scryfall REST calls — otags, prices, rarity, image, color identity search |
| `services/analysis.py` | CREATE | Pure TF computation and Buzzword Score ranking |
| `templates/base.html` | CREATE | Shared layout — nav, CSS/JS links, flash messages |
| `templates/index.html` | CREATE | Landing page — commander search form |
| `templates/commander.html` | CREATE | Commander page — EDHRec list + Slept On + controls |
| `templates/error.html` | CREATE | User-friendly error page |
| `static/css/style.css` | CREATE | App styles — card grid, sections, filter controls |
| `static/js/filters.js` | CREATE | Client-side filter logic — N slider, inclusion cap, price cap, pauper toggle |
| `export.py` | CREATE | Static HTML generator → `/docs` folder |

---

## Tasks

Execute in order. Each task is atomic and verifiable.

---

### Task 1: Install dependencies and create requirements.txt
- **File**: `requirements.txt`
- **Action**: CREATE
- **Implement**:
  ```
  flask>=3.0
  pyedhrec==0.0.2
  requests>=2.31
  frozen-flask>=1.0
  ```
  Then run: `pip install -r requirements.txt`
- **Validate**: `python -c "import flask, pyedhrec, requests; print('OK')`

---

### Task 2: Create services package
- **File**: `services/__init__.py`
- **Action**: CREATE
- **Implement**: Empty file (package marker only)
- **Validate**: `python -c "import services"`

---

### Task 3: Implement services/edhrec.py
- **File**: `services/edhrec.py`
- **Action**: CREATE
- **Implement**:
  - Import `pyedhrec` and `logging`
  - `slugify(name: str) -> str` — lowercases, replaces spaces/apostrophes/commas with hyphens, strips non-alphanumeric (except hyphens)
  - `get_commander_cards(commander_name: str) -> list[dict]` — calls PyEDHRec, returns list of card dicts with keys: `name`, `edhrec_synergy` (float 0–1), `edhrec_inclusion` (float 0–1), `edhrec_category` (str). Sets `otags=[]`, `price_usd=None`, `rarity=""`, `image_uri=""`, `buzzword_score=0.0`.
  - `get_commander_info(commander_name: str) -> dict | None` — returns `{name, color_identity: list[str]}` for the commander itself, or `None` on failure.
  - Wrap all PyEDHRec calls in try/except; log errors; return `[]` or `None` on failure.
  - **PyEDHRec usage note:** The library's API is `pyedhrec.EDHRec()`. Inspect the installed source to confirm method names before writing calls. Likely: `EDHRec().get_commander_cards(slug)`. If the library is insufficient, fall back to: `requests.get(f"https://json.edhrec.com/pages/commanders/{slug}.json")` and parse the JSON response manually.
- **Validate**: `python -c "from services.edhrec import get_commander_cards; cards = get_commander_cards('Atraxa, Praetors Voice'); print(len(cards), 'cards')"`

---

### Task 4: Implement services/scryfall.py
- **File**: `services/scryfall.py`
- **Action**: CREATE
- **Implement**:
  - `SCRYFALL_BASE = "https://api.scryfall.com"`
  - Module-level cache: `_card_cache: dict[str, dict] = {}`
  - `_get_card(name: str) -> dict | None` — hits `GET /cards/named?exact={name}`, caches result, sleeps 0.1s, returns raw Scryfall card object or `None`
  - `get_card_details(name: str) -> dict` — calls `_get_card`, extracts and returns: `{"otags": list[str], "price_usd": float|None, "rarity": str, "image_uri": str}`. otags come from `card["keywords"]` + `card.get("produced_mana", [])` ... **actually**: Scryfall otags are in the `oracle_tags` field available via `/cards/{id}/rulings` — no, they are available as `card["keywords"]` is not the same. **Correct approach:** Use the Scryfall tagger endpoint: `GET https://tagger.scryfall.com/card/{set}/{number}/tags` is unofficial. The correct official approach is: search `https://api.scryfall.com/cards/search?q=oracletag%3Aramp+name%3A"Sol+Ring"` — but that's per-tag not per-card. **Best approach for per-card otags:** `GET https://api.scryfall.com/cards/named?exact={name}` returns the card; then fetch `GET https://tagger.scryfall.com/card/{card.set}/{card.collector_number}` — this is the tagger page. Alternatively, use bulk data. **Practical decision:** Use Scryfall's `/cards/search` with `q=unique:prints+name:"{name}"` to get the card, then use the `oracle_id` to query `https://api.scryfall.com/cards/search?q=oracleid:{oracle_id}` for tags. **Simplest correct approach:** Hit `https://api.scryfall.com/cards/named?fuzzy={name}` for the card object, then hit `https://tagger.scryfall.com/card/{set}/{number}/taggings` which returns JSON with tags. Implement with a fallback: if tagger endpoint fails or returns non-JSON, set `otags=[]` and continue.
  - `get_color_identity_pool(color_identity: list[str]) -> list[dict]` — searches Scryfall for all cards matching `id<={color_string}` (e.g., `id<=WUBGR`), paginates through all results, returns list of card dicts with same shape as above. Limit to legal Commander cards: add `f:edh` to the query. Paginate using `next_page` from Scryfall response. Sleep 0.1s between pages.
  - All functions catch `requests.RequestException` and log errors; return `None`/`[]` on failure.
- **Validate**: `python -c "from services.scryfall import get_card_details; print(get_card_details('Sol Ring'))"`

---

### Task 5: Implement services/analysis.py
- **File**: `services/analysis.py`
- **Action**: CREATE
- **Implement**:
  - `compute_tf(edhrec_cards: list[dict]) -> dict[str, float]` — for each card in edhrec_cards, for each otag in `card["otags"]`, add `card["edhrec_synergy"]` to `tf[otag]`. Return the tf dict.
  - `score_cards(color_pool: list[dict], tf: dict[str, float], edhrec_card_names: set[str]) -> list[dict]` — for each card in color_pool not in edhrec_card_names, compute `buzzword_score = sum(tf.get(tag, 0.0) for tag in card["otags"])`. Set `card["buzzword_score"] = buzzword_score`. Return list sorted descending by buzzword_score, excluding cards with score == 0.
  - `apply_inclusion_cap(slept_on: list[dict], cap: float) -> list[dict]` — filters out cards where `card["edhrec_inclusion"] > cap`. Note: Slept On cards from the color pool will have `edhrec_inclusion = 0.0` by default (they're not in the EDHRec list) — this filter primarily prevents borderline cards from showing. Leave as-is; the filter is mainly meaningful if we later cross-reference EDHRec inclusion for color pool cards.
  - No imports from `flask`, `requests`, or any service — pure functions only.
- **Validate**: `python -c "from services.analysis import compute_tf, score_cards; print('OK')"`

---

### Task 6: Implement app.py
- **File**: `app.py`
- **Action**: CREATE
- **Implement**:
  ```python
  from flask import Flask, render_template, request, redirect, url_for
  from services import edhrec, scryfall, analysis

  app = Flask(__name__)

  @app.route("/", methods=["GET", "POST"])
  def index():
      if request.method == "POST":
          name = request.form.get("commander", "").strip()
          if name:
              return redirect(url_for("commander", slug=edhrec.slugify(name)))
      return render_template("index.html")

  @app.route("/commander/<slug>")
  def commander(slug):
      # 1. Fetch EDHRec cards
      cards = edhrec.get_commander_cards(slug)
      if not cards:
          return render_template("error.html", message=f"No EDHRec data found for '{slug}'."), 404

      # 2. Enrich with Scryfall data
      for card in cards:
          details = scryfall.get_card_details(card["name"])
          if details:
              card.update(details)

      # 3. Get commander color identity
      commander_info = edhrec.get_commander_info(slug)
      color_identity = commander_info["color_identity"] if commander_info else ["W","U","B","R","G"]

      # 4. Fetch color pool
      color_pool = scryfall.get_color_identity_pool(color_identity)

      # 5. Enrich color pool with Scryfall details
      edhrec_names = {c["name"] for c in cards}
      for card in color_pool:
          if card["name"] not in edhrec_names:
              details = scryfall.get_card_details(card["name"])
              if details:
                  card.update(details)

      # 6. Compute TF and score
      tf = analysis.compute_tf(cards)
      slept_on = analysis.score_cards(color_pool, tf, edhrec_names)

      return render_template(
          "commander.html",
          slug=slug,
          edhrec_cards=cards,
          slept_on=slept_on,
          tf=tf,
      )

  if __name__ == "__main__":
      app.run(debug=True)
  ```
- **Validate**: `flake8 app.py && python -m py_compile app.py`

---

### Task 7: Create templates/base.html
- **File**: `templates/base.html`
- **Action**: CREATE
- **Implement**: Standard HTML5 base template with:
  - `<title>{% block title %}MTG EDH Sleeper Picks{% endblock %}</title>`
  - Link to `/static/css/style.css`
  - Nav bar: "MTG EDH Sleeper Picks" title linking to `/`
  - `{% block content %}{% endblock %}`
  - Script tag for `/static/js/filters.js` at bottom of body (only on commander page — use `{% block scripts %}{% endblock %}`)
- **Validate**: File exists and is valid HTML5 skeleton

---

### Task 8: Create templates/index.html
- **File**: `templates/index.html`
- **Action**: CREATE
- **Implement**:
  - Extends `base.html`
  - Centered hero section with app title and tagline
  - `<form method="POST" action="/">` with text input `name="commander"` and submit button
  - Placeholder text: "Search for a commander (e.g., Atraxa, Praetors' Voice)"
- **Validate**: `python app.py` (brief start), visit `localhost:5000`, form renders

---

### Task 9: Create templates/error.html
- **File**: `templates/error.html`
- **Action**: CREATE
- **Implement**:
  - Extends `base.html`
  - Shows `{{ message }}` in a styled error box
  - Link back to home
- **Validate**: File exists

---

### Task 10: Create templates/commander.html
- **File**: `templates/commander.html`
- **Action**: CREATE
- **Implement**:

  **Controls bar** (sticky or top of page):
  - Price cap: `<input type="number" id="price-cap" min="0" step="0.01" placeholder="Max price ($)">` 
  - Pauper toggle: `<label><input type="checkbox" id="pauper-toggle"> Pauper only</label>`

  **EDHRec Section:**
  - `<section id="edhrec-section">`
  - Group cards by `edhrec_category` using Jinja `groupby`
  - Per-category `<h3>` heading
  - Card grid: for each card render a `.card-item` div with data attributes:
    ```html
    <div class="card-item"
         data-price="{{ card.price_usd or 9999 }}"
         data-rarity="{{ card.rarity }}">
      <img src="{{ card.image_uri }}" alt="{{ card.name }}">
      <div class="card-info">
        <strong>{{ card.name }}</strong>
        <span>Synergy: {{ (card.edhrec_synergy * 100)|int }}%</span>
        <span>Inclusion: {{ (card.edhrec_inclusion * 100)|int }}%</span>
        <span>${{ "%.2f"|format(card.price_usd) if card.price_usd else "N/A" }}</span>
        <span>{{ card.rarity|capitalize }}</span>
      </div>
    </div>
    ```

  **Slept On Section:**
  - `<section id="slept-on-section">`
  - Controls:
    - `<input type="range" id="n-slider" min="1" max="100" value="50">` with live label showing current value
    - `<input type="range" id="inclusion-cap" min="0" max="100" value="10">` with live label (shows "X% inclusion cap")
  - Card list (same `.card-item` structure) with additional data attribute:
    ```html
    data-inclusion="{{ (card.edhrec_inclusion * 100)|int }}"
    data-score="{{ "%.2f"|format(card.buzzword_score) }}"
    ```
  - Show Buzzword Score on each card: `<span>Score: {{ "%.1f"|format(card.buzzword_score) }}</span>`

- **Validate**: `python app.py`, search Atraxa, verify both sections appear with data

---

### Task 11: Create static/css/style.css
- **File**: `static/css/style.css`
- **Action**: CREATE
- **Implement**:
  - CSS custom properties for colors (dark background, card surface, accent)
  - `.card-item`: display grid or inline-block, fixed width ~200px, card image 100% width, rounded corners, subtle shadow
  - `.card-item.hidden`: `display: none`
  - `.card-grid`: flexbox wrap
  - Controls bar: flexbox row, sticky top, background, padding
  - Section headings styled distinctly (EDHRec vs Slept On)
  - Responsive enough for a desktop browser tab (no mobile requirement)
- **Validate**: Visual check — cards display in a grid, not stacked vertically

---

### Task 12: Create static/js/filters.js
- **File**: `static/js/filters.js`
- **Action**: CREATE
- **Implement**:
  ```javascript
  // Runs after DOM loaded
  document.addEventListener("DOMContentLoaded", () => {
    const priceCapInput = document.getElementById("price-cap");
    const pauperToggle = document.getElementById("pauper-toggle");
    const nSlider = document.getElementById("n-slider");
    const nLabel = document.getElementById("n-label");
    const inclusionSlider = document.getElementById("inclusion-cap");
    const inclusionLabel = document.getElementById("inclusion-label");

    function applyFilters() {
      const maxPrice = parseFloat(priceCapInput.value) || Infinity;
      const pauperOnly = pauperToggle.checked;
      const maxN = parseInt(nSlider.value);
      const maxInclusion = parseInt(inclusionSlider.value);

      // EDHRec section — price and pauper only
      document.querySelectorAll("#edhrec-section .card-item").forEach(card => {
        const price = parseFloat(card.dataset.price);
        const rarity = card.dataset.rarity;
        const hidden = price > maxPrice || (pauperOnly && rarity !== "common");
        card.classList.toggle("hidden", hidden);
      });

      // Slept On section — price, pauper, inclusion cap, and N limit
      let shown = 0;
      document.querySelectorAll("#slept-on-section .card-item").forEach(card => {
        const price = parseFloat(card.dataset.price);
        const rarity = card.dataset.rarity;
        const inclusion = parseInt(card.dataset.inclusion);
        const overFilters = price > maxPrice
          || (pauperOnly && rarity !== "common")
          || inclusion > maxInclusion;
        const overN = shown >= maxN;
        const hidden = overFilters || overN;
        card.classList.toggle("hidden", hidden);
        if (!hidden) shown++;
      });

      if (nLabel) nLabel.textContent = maxN;
      if (inclusionLabel) inclusionLabel.textContent = maxInclusion + "%";
    }

    priceCapInput?.addEventListener("input", applyFilters);
    pauperToggle?.addEventListener("change", applyFilters);
    nSlider?.addEventListener("input", applyFilters);
    inclusionSlider?.addEventListener("input", applyFilters);

    applyFilters(); // apply defaults on load
  });
  ```
- **Validate**: In browser, drag N slider — Slept On cards hide/show immediately. Toggle pauper — only commons remain visible.

---

### Task 13: Create export.py
- **File**: `export.py`
- **Action**: CREATE
- **Implement**:
  ```python
  """
  Static site generator for GitHub Pages.
  Usage: python export.py <commander_name> [<commander_name> ...]
  Output: /docs/<slug>.html and /docs/index.html
  """
  import sys
  import os
  from pathlib import Path
  from app import app
  from services import edhrec

  DOCS_DIR = Path("docs")
  DOCS_DIR.mkdir(exist_ok=True)

  def export_commander(name: str):
      slug = edhrec.slugify(name)
      with app.test_client() as client:
          response = client.get(f"/commander/{slug}")
          if response.status_code == 200:
              out_path = DOCS_DIR / f"{slug}.html"
              out_path.write_bytes(response.data)
              print(f"Exported: {out_path}")
          else:
              print(f"Failed ({response.status_code}): {slug}")

  def export_index():
      with app.test_client() as client:
          response = client.get("/")
          if response.status_code == 200:
              (DOCS_DIR / "index.html").write_bytes(response.data)
              print("Exported: docs/index.html")

  if __name__ == "__main__":
      commanders = sys.argv[1:] or []
      export_index()
      for name in commanders:
          export_commander(name)
  ```
  Note: Static assets (`/static/`) need to be copied to `/docs/static/` or paths adjusted. Add a copy step using `shutil.copytree("static", DOCS_DIR / "static", dirs_exist_ok=True)`.
- **Validate**: `python export.py "Atraxa, Praetors' Voice"` creates `docs/atraxa-praetors-voice.html`

---

### Task 14: Smoke test the full flow
- **Action**: VERIFY (no file changes)
- **Steps**:
  1. `python app.py`
  2. Open `http://localhost:5000`
  3. Search "Atraxa, Praetors' Voice"
  4. Verify EDHRec section shows grouped cards with images, synergy %, inclusion %, prices
  5. Verify Slept On section shows scored cards
  6. Test: price cap input hides expensive cards
  7. Test: pauper toggle hides non-commons
  8. Test: N slider changes Slept On count
  9. Test: inclusion cap slider adjusts Slept On
- **Validate**: All 9 steps pass without console errors

---

### Task 15: Run lint validation
- **Action**: VALIDATE
- **Implement**: 
  ```bash
  flake8 app.py services/ export.py
  python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py export.py
  ```
- **Validate**: Zero errors from both commands

---

## Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| PyEDHRec 0.0.2 method names are unknown until runtime | In Task 3, inspect `pyedhrec` source after install: `python -c "import inspect, pyedhrec; print(inspect.getsource(pyedhrec))"`. Fall back to direct EDHRec JSON API if library is insufficient. |
| Scryfall otag endpoint is unofficial (tagger.scryfall.com) | Wrap in try/except returning `[]` on failure. Cards without otags get score 0 and don't appear in Slept On — graceful degradation. |
| Color identity pool fetch (all legal EDH cards) may take minutes | In MVP, warn user with a loading message. For export.py, this is fine since it's a one-time operation. |
| `edhrec_inclusion` for color pool cards is unknown (they're not in the EDHRec list) | Default to `0.0`. The inclusion cap filter is most useful for borderline EDHRec cards if we later cross-reference. Document the limitation in a comment in `analysis.py`. |

---

## Validation Sequence

```bash
# After all tasks complete, run in order:
flake8 app.py services/ export.py
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py export.py
python app.py  # manual smoke test
```

---

## Acceptance Criteria

- [ ] All 15 tasks completed
- [ ] `flake8` passes with zero errors on all Python files
- [ ] `py_compile` passes on all Python files
- [ ] Commander search returns results for Atraxa, Praetors' Voice
- [ ] EDHRec section shows cards with images, synergy %, inclusion %, price, rarity
- [ ] Slept On section shows scored cards distinct from EDHRec list
- [ ] N slider, inclusion cap slider, price cap input, and pauper toggle all work without page reload
- [ ] `export.py` produces a valid HTML file in `/docs`
- [ ] No bare `print()` calls in `app.py` or `services/` (use `app.logger` or omit)
- [ ] No business logic inside route functions or templates
