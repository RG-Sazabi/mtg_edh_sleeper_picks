# MTG EDH Sleeper Picks

Surfaces underplayed Commander cards using weighted Scryfall oracle-tag analysis vs. EDHRec recommendations.

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

Open http://localhost:5000, search for a commander, and wait ~30–120 seconds for the analysis to load (Scryfall data fetch).

## How It Works

1. Fetches EDHRec recommended cards for the commander via PyEDHRec.
2. Enriches each card with Scryfall oracle tags, price (TCGPlayer via Scryfall), and rarity.
3. Runs weighted term-frequency analysis: tags on high-synergy EDHRec cards get higher scores.
4. Scores every card in the commander's color identity by how many high-value tags it shares.
5. Displays the standard EDHRec list plus a **Slept On** section of top-scoring underplayed cards.
