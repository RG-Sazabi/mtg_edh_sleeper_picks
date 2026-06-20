# Plan: Issue #3 — Flask App, Routes, and Jinja2 Templates

## Summary
Create `app.py` with two routes (`/` search landing, `/commander/<slug>` analysis page) and four Jinja2 templates (`base.html`, `index.html`, `commander.html`, `error.html`). The commander route orchestrates the full pipeline: fetch EDHRec cards → enrich via Scryfall → fetch color pool → score → render. Templates include all `data-*` attributes and control element `id`s that Issue #4's `filters.js` will target. No CSS or JS logic in this issue — just structure and data rendering.

## User Story
As a deckbuilder, I want to open a browser, search for a commander, and see both the EDHRec recommended cards and the Slept On section rendered on a single page, so that I have everything I need in one place.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | MEDIUM |
| GitHub Issue | #3 |
| Systems Affected | app.py (new), templates/ (4 new files), static/css/style.css (stub), static/js/filters.js (stub) |

---

## Important Notes Before Writing Code

### Route performance
The `/commander/<slug>` route loads the otag index (17MB, one-time) then fetches the full color identity pool from Scryfall (paginated, ~30–120s depending on color identity size). Flask's dev server has no timeout on GET requests — this is fine. Do NOT add artificial timeouts or async complexity.

### `edhrec.get_commander_cards()` takes the commander's display name, not a slug
The route receives a slug (e.g. `atraxa-praetors-voice`). We must reconstruct the name for PyEDHRec. Strategy: use `edhrec.get_commander_info(slug)` which hits the EDHRec JSON endpoint — its `name` field is the canonical display name. Then pass that name to `get_commander_cards()`.

Actually, `get_commander_info` calls `slugify(commander_name)` internally. So we can pass the slug directly to both functions since `slugify("atraxa-praetors-voice")` = `"atraxa-praetors-voice"` (no change needed — already slugified). Verified: `slugify` only does lowercase + replace spaces/apostrophes/commas. A slug passed directly works fine.

### Scryfall enrichment strategy
Enriching every EDHRec card individually with `get_card_details()` is slow (1 request per card, 0.1s sleep each, ~100+ cards = 10+ seconds). This is acceptable — personal tool. Do it sequentially in the route.

### `data-price` sentinel for cards with no price
Cards where `price_usd is None` need a sentinel value for the JS price-cap filter. Use `data-price="9999"` so they are never hidden by default.

### Template `id` contract with filters.js (Issue #4)
These exact `id` values must appear in `commander.html` — Issue #4 JS will target them:
- `#price-cap` — price cap number input
- `#pauper-toggle` — pauper checkbox
- `#n-slider` — Slept On count range input
- `#n-label` — live display of N value
- `#inclusion-cap` — inclusion cap range input
- `#inclusion-label` — live display of inclusion cap %

### Card `.card-item` class contract with filters.js
Every card `div` must have:
- class `card-item`
- `data-price` — float string or "9999"
- `data-rarity` — "common" | "uncommon" | "rare" | "mythic" | ""
- `data-inclusion` — integer 0–100 (percentage, not fraction)

Slept On cards additionally need:
- `data-score` — float string buzzword score

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `app.py` | CREATE | Flask app — two routes |
| `templates/base.html` | CREATE | Shared layout |
| `templates/index.html` | CREATE | Landing page with search form |
| `templates/commander.html` | CREATE | Commander analysis page |
| `templates/error.html` | CREATE | Error page |
| `static/css/style.css` | CREATE | Empty stub (Issue #4 will fill it) |
| `static/js/filters.js` | CREATE | Empty stub (Issue #4 will fill it) |

---

## Tasks

### Task 1: Create static stubs
- **Files**: `static/css/style.css`, `static/js/filters.js`
- **Action**: CREATE both as empty files so Flask can serve them without 404 during testing.
- **Implement**: Each file contains a single comment line:
  - `style.css`: `/* styles — added in Issue #4 */`
  - `filters.js`: `/* filters — added in Issue #4 */`
- **Validate**: Files exist at those paths.

---

### Task 2: Create templates/base.html
- **File**: `templates/base.html`
- **Action**: CREATE
- **Implement**:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}MTG EDH Sleeper Picks{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
  <nav>
    <a href="{{ url_for('index') }}">MTG EDH Sleeper Picks</a>
  </nav>
  <main>
    {% block content %}{% endblock %}
  </main>
  {% block scripts %}{% endblock %}
</body>
</html>
```
- **Validate**: File exists and is valid HTML5 skeleton.

---

### Task 3: Create templates/index.html
- **File**: `templates/index.html`
- **Action**: CREATE
- **Implement**:
```html
{% extends "base.html" %}
{% block title %}Search — MTG EDH Sleeper Picks{% endblock %}
{% block content %}
<h1>MTG EDH Sleeper Picks</h1>
<p>Find underplayed cards for your Commander deck.</p>
<form method="POST" action="{{ url_for('index') }}">
  <input type="text" name="commander" placeholder="e.g. Atraxa, Praetors' Voice" required autofocus>
  <button type="submit">Analyze</button>
</form>
{% endblock %}
```
- **Validate**: File exists.

---

### Task 4: Create templates/error.html
- **File**: `templates/error.html`
- **Action**: CREATE
- **Implement**:
```html
{% extends "base.html" %}
{% block title %}Error — MTG EDH Sleeper Picks{% endblock %}
{% block content %}
<h1>Something went wrong</h1>
<p>{{ message }}</p>
<a href="{{ url_for('index') }}">Back to search</a>
{% endblock %}
```
- **Validate**: File exists.

---

### Task 5: Create templates/commander.html
- **File**: `templates/commander.html`
- **Action**: CREATE
- **Implement** the full commander page. Key structural points:

**Controls bar** (rendered once at top, before sections):
```html
<div id="controls">
  <label>Max price: $<input type="number" id="price-cap" min="0" step="0.01" placeholder="any"></label>
  <label><input type="checkbox" id="pauper-toggle"> Pauper only (commons)</label>
</div>
```

**EDHRec section** — group by category using Jinja `groupby`:
```html
<section id="edhrec-section">
  <h2>EDHRec Recommendations</h2>
  {% for category, cat_cards in edhrec_cards | groupby("edhrec_category") %}
  <h3>{{ category }}</h3>
  <div class="card-grid">
    {% for card in cat_cards %}
    <div class="card-item"
         data-price="{{ card.price_usd if card.price_usd is not none else 9999 }}"
         data-rarity="{{ card.rarity }}"
         data-inclusion="{{ (card.edhrec_inclusion * 100) | int }}">
      <img src="{{ card.image_uri }}" alt="{{ card.name }}" loading="lazy">
      <div class="card-info">
        <strong>{{ card.name }}</strong>
        <span>Synergy: {{ (card.edhrec_synergy * 100) | round(1) }}%</span>
        <span>Inclusion: {{ (card.edhrec_inclusion * 100) | round(1) }}%</span>
        <span>Price: {% if card.price_usd %}${{ "%.2f" | format(card.price_usd) }}{% else %}N/A{% endif %}</span>
        <span>{{ card.rarity | capitalize }}</span>
      </div>
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</section>
```

**Slept On section** — controls + card list:
```html
<section id="slept-on-section">
  <h2>Slept On</h2>
  <p>Cards outside the EDHRec list with the highest functional overlap.</p>
  <div id="slept-on-controls">
    <label>Show top <input type="range" id="n-slider" min="1" max="100" value="50">
      <span id="n-label">50</span> cards</label>
    <label>Inclusion cap: <input type="range" id="inclusion-cap" min="0" max="100" value="10">
      <span id="inclusion-label">10</span>%</label>
  </div>
  <div class="card-grid" id="slept-on-grid">
    {% for card in slept_on %}
    <div class="card-item"
         data-price="{{ card.price_usd if card.price_usd is not none else 9999 }}"
         data-rarity="{{ card.rarity }}"
         data-inclusion="{{ (card.edhrec_inclusion * 100) | int }}"
         data-score="{{ card.buzzword_score }}">
      <img src="{{ card.image_uri }}" alt="{{ card.name }}" loading="lazy">
      <div class="card-info">
        <strong>{{ card.name }}</strong>
        <span>Score: {{ card.buzzword_score | round(2) }}</span>
        <span>Price: {% if card.price_usd %}${{ "%.2f" | format(card.price_usd) }}{% else %}N/A{% endif %}</span>
        <span>{{ card.rarity | capitalize }}</span>
        <span>Tags: {{ card.otags[:3] | join(", ") }}{% if card.otags | length > 3 %}…{% endif %}</span>
      </div>
    </div>
    {% endfor %}
  </div>
</section>
```

**Scripts block** at bottom:
```html
{% block scripts %}
<script src="{{ url_for('static', filename='js/filters.js') }}"></script>
{% endblock %}
```

- **Validate**: File exists with all required `id` attributes and `data-*` attributes.

---

### Task 6: Create app.py
- **File**: `app.py`
- **Action**: CREATE
- **Implement**:

```python
import logging

from flask import Flask, render_template, request, redirect, url_for

from services import edhrec, scryfall, analysis

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("commander", "").strip()
        if name:
            return redirect(url_for("commander", slug=edhrec.slugify(name)))
    return render_template("index.html")


@app.route("/commander/<slug>")
def commander(slug):
    # 1. Fetch commander info (color identity, display name)
    info = edhrec.get_commander_info(slug)
    if not info:
        return render_template("error.html", message=f"Commander '{slug}' not found on EDHRec."), 404

    # 2. Fetch EDHRec recommended cards
    edhrec_cards = edhrec.get_commander_cards(slug)
    if not edhrec_cards:
        return render_template("error.html", message=f"No card data found for '{slug}'."), 404

    # 3. Enrich each EDHRec card with Scryfall data (otags, price, rarity, image)
    scryfall._load_otag_index()
    for card in edhrec_cards:
        details = scryfall.get_card_details(card["name"])
        card.update(details)

    # 4. Fetch all EDH-legal cards in the commander's color identity
    color_pool = scryfall.get_color_identity_pool(info["color_identity"])

    # 5. Score color pool against EDHRec TF weights
    edhrec_names = {c["name"] for c in edhrec_cards}
    tf = analysis.compute_tf(edhrec_cards)
    slept_on = analysis.score_cards(color_pool, tf, edhrec_names)

    return render_template(
        "commander.html",
        commander=info,
        edhrec_cards=edhrec_cards,
        slept_on=slept_on,
    )


if __name__ == "__main__":
    app.run(debug=True)
```

- **Validate**: `"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -m py_compile app.py`

---

### Task 7: Lint check
- **Action**: VALIDATE
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" app.py --max-line-length=119
  ```
- Fix all errors.

---

### Task 8: Smoke test — start server and verify routes render
- **Action**: VALIDATE (manual)
- **Steps**:
  1. Run `"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" app.py`
  2. Open `http://localhost:5000` — verify search form renders
  3. Submit "Atraxa, Praetors' Voice" — verify redirect to `/commander/atraxa-praetors-voice`
  4. Wait for page to load (30–120s, network dependent)
  5. Verify EDHRec section shows cards grouped by category
  6. Verify Slept On section shows scored cards
  7. Verify each card has an image, name, and stats
  8. Verify control elements are present: `#price-cap`, `#pauper-toggle`, `#n-slider`, `#inclusion-cap`
  9. Navigate to an invalid slug (e.g. `/commander/not-a-real-card`) — verify error page renders cleanly

---

## Validation Sequence

```bash
# 1. Compile check
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -m py_compile app.py

# 2. Lint
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" app.py --max-line-length=119

# 3. Manual smoke test (Task 8)
```

---

## Acceptance Criteria

- [ ] `app.py` exists with `/` (GET+POST) and `/commander/<slug>` routes
- [ ] Routes contain no business logic — all data work done in `services/`
- [ ] `app.logger` (via `logging.basicConfig`) used — no bare `print()` in app.py
- [ ] `templates/base.html` — valid HTML5, links to `style.css`, has `{% block scripts %}`
- [ ] `templates/index.html` — extends base, has search form POST to `/`
- [ ] `templates/commander.html` — EDHRec section grouped by `edhrec_category`, Slept On section with controls
- [ ] `templates/error.html` — renders `{{ message }}`, links back to index
- [ ] Every card div has class `card-item` and `data-price`, `data-rarity`, `data-inclusion` attributes
- [ ] Slept On cards additionally have `data-score` attribute
- [ ] Control elements present with exact IDs: `price-cap`, `pauper-toggle`, `n-slider`, `n-label`, `inclusion-cap`, `inclusion-label`
- [ ] `static/css/style.css` and `static/js/filters.js` stubs exist (no 404 on page load)
- [ ] `python app.py` starts; searching "Atraxa, Praetors' Voice" returns a populated page
- [ ] Invalid slug returns error.html with 404
- [ ] `flake8 app.py --max-line-length=119` passes with zero errors
- [ ] Resolves GitHub Issue #3
