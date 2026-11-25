# MTG EDH Sleeper Picks

A local Flask app for Commander deckbuilding. It shows a commander's EDHRec
recommendations and adds a **Slept On** tab: underplayed cards in the commander's
color identity that share the features (Scryfall oracle tags, optionally card
types) its decks over-use, scored with a feature-lift model (each feature weighted
by how much more the commander plays it than its color-identity baseline).

## Local Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\pip install -r requirements.txt
# macOS/Linux:
.venv/bin/pip install -r requirements.txt
```

## Run Locally

```bash
# Windows:
.venv\Scripts\python app.py
# macOS/Linux:
.venv/bin/python app.py
```

Open http://localhost:5000 and search for a commander (or paste an Archidekt deck
URL). On first start the app downloads Scryfall's card data (~87 MB, gzip JSON
Lines) into `cache/` and refreshes it daily; that takes a few seconds to a minute
depending on your connection. After that a commander page loads in a few seconds
(one EDHRec request plus local computation). The footer shows the date of the
card data in use.

## Tests

```bash
.venv\Scripts\python -m pytest          # offline suite, a few seconds
.venv\Scripts\python -m pytest -m live  # canary against the real services
```
