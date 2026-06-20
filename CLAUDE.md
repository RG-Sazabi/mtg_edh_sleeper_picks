# CLAUDE.md

## Project Overview

**MTG EDH Sleeper Picks** — a locally hosted Flask web app for Magic: The Gathering players building Commander decks. It replicates the EDHRec commander page, then adds a "Slept On" section that surfaces underplayed cards with high functional overlap to the recommended list, scored via weighted term-frequency analysis of Scryfall oracle tags (otags).

**Workflow summary:**
1. User searches for a commander by name on the landing page.
2. App fetches EDHRec data for that commander via PyEDHRec.
3. For each recommended card, app fetches Scryfall data (otags, price, rarity).
4. TF analysis: count otag frequency across all recommended cards, weighting each card's contribution by its EDHRec synergy score.
5. For every card in the commander's color identity (queried from Scryfall), compute a **Buzzword Score** = sum of TF-weighted otag values the card shares with the recommended set.
6. Display the standard EDHRec card list plus a "Slept On" section of top-N cards by Buzzword Score, filtered by inclusion threshold, price cap, and rarity.

**Deployment:** Flask dev server for local use. Static HTML export (via `flask freeze` / custom script) for GitHub Pages hosting.

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| Flask | 3.x | Web server and routing |
| Jinja2 | bundled with Flask | HTML templating |
| pyedhrec | 0.0.2 | Fetch EDHRec commander data |
| Scryfall API | REST (no key needed) | Card otags, prices (TCGPlayer via Scryfall), rarity, color identity search |
| Frozen-Flask or custom export | latest | Static HTML export for GitHub Pages |

**Scryfall pricing note:** Scryfall card objects include `prices.usd` (TCGPlayer market price). No TCGPlayer API key needed.

---

## Commands

```bash
# Development — start local Flask server
python app.py

# Lint / Format
flake8 .                  # Check for errors
black .                   # Auto-format

# Static export (GitHub Pages)
python export.py          # Generates /docs folder for GitHub Pages
```

---

## Self-Correction Workflow

After writing or modifying ANY code, always run:

```bash
flake8 . && python -m py_compile <changed_file>.py
```

Read every error. Fix every error. Re-run until the output is clean.
**Never report a task as complete if lint or type checking fails.**

---

## Architecture

```
mtg_edh_sleeper_picks/
├── app.py                  # Flask app — routes only, calls services
├── services/
│   ├── edhrec.py           # PyEDHRec calls; returns structured card list
│   ├── scryfall.py         # Scryfall API calls; otags, prices, color identity search
│   └── analysis.py         # TF analysis and Buzzword Score computation
├── templates/
│   ├── base.html           # Shared layout, nav, CSS links
│   ├── index.html          # Landing page with search bar
│   └── commander.html      # Commander page: EDHRec list + Slept On section
├── static/
│   ├── css/style.css
│   └── js/filters.js       # Client-side price/rarity filter logic
├── export.py               # Static site generator for GitHub Pages → /docs
├── requirements.txt
└── memory/                 # Persistent agent memory (do not delete)
```

**Layer rules:**
- `app.py` — routes only; never contains business logic or API calls directly.
- `services/edhrec.py` — all PyEDHRec calls; returns plain dicts/lists.
- `services/scryfall.py` — all Scryfall HTTP calls; handles rate limiting and caching.
- `services/analysis.py` — pure computation; no I/O, no API calls.
- Templates — display only; no data transformation.

---

## Key Data Structures

```python
# Card as passed between services
{
  "name": str,
  "edhrec_synergy": float,      # e.g. 0.42 — from PyEDHRec
  "edhrec_inclusion": float,    # e.g. 0.34 — fraction of decks (0–1)
  "otags": list[str],           # e.g. ["ramp", "draw", "removal"]
  "price_usd": float | None,    # TCGPlayer price via Scryfall
  "rarity": str,                # "common" | "uncommon" | "rare" | "mythic"
  "buzzword_score": float,      # computed in analysis.py; 0 for EDHRec cards
  "image_uri": str,             # Scryfall card image URL
}
```

---

## Feature Spec

### Landing Page (`/`)
- Search bar: autocomplete or plain text input for commander name.
- On submit: POST/redirect to `/commander/<slug>`.

### Commander Page (`/commander/<slug>`)
**EDHRec Section** — mirrors standard EDHRec layout:
- Cards grouped by category (ramp, draw, removal, etc.).
- Each card shows: image, name, synergy %, inclusion %, price, rarity.

**Slept On Section:**
- Top-N cards by Buzzword Score (default N=50, slider to adjust 1–100).
- Exclusion: cards already in the EDHRec list are not shown here.
- Inclusion cap filter: exclude cards where `edhrec_inclusion > threshold` (default 10% = 0.10, adjustable slider).
- Sorted descending by Buzzword Score.
- Same card display as EDHRec section.

**Filters (apply to both sections):**
- Price cap: numeric input or slider (e.g., hide cards > $X.XX).
- Pauper toggle: when ON, show only common-rarity cards.

### Static Export (`/docs`)
- `export.py` renders each commander page to a static `.html` file under `/docs`.
- GitHub Pages is configured to serve from `/docs` on `master`.

---

## Code Patterns

### Naming Conventions
- Files: `snake_case.py` for Python, `kebab-case.css/js` for static assets
- Variables / functions: `snake_case`
- Constants: `SCREAMING_SNAKE_CASE`
- URL slugs: `kebab-case` (e.g., `atraxa-praetors-voice`)

### Error Handling
- Scryfall and PyEDHRec calls should catch HTTP errors and return `None` or empty structures rather than raising to the route.
- Routes return a user-friendly error page on `None` data, not a 500.
- Log errors with `app.logger.error(...)` — no bare `print()` in production paths.

### Scryfall Bulk Data (local store)
- Card attributes, oracle tags, and the color-identity pool are served from a **local bulk store** (`services/bulk.py`), not per-request HTTP. On first use it downloads Scryfall's `default_cards` (~547 MB) and `oracle_tags` (~18 MB) bulk files to `cache/` and builds in-memory indices (stream-parsed with `ijson` to bound memory). Files refresh when older than 24h.
- We use `default_cards` (every paper printing) rather than `oracle_cards` (one printing per card) so each card renders its **cleanest standard printing**. `oracle_cards`' "most recent recognizable" pick is a borderless/full-art/Un-set/art-series version for ~12% of cards (often missing the normal frame or rules text). `bulk._printing_penalty` ranks printings; we keep the lowest-penalty one per oracle id, tie-broken toward high-res + newest. Do not switch back to `oracle_cards`.
- `cache/` is downloaded **reference data** (the full Scryfall catalog), intentionally persisted to disk and gitignored. This is distinct from per-request response caching — the earlier "no disk cache" guidance does not apply to the bulk store.
- After warm-up, a commander lookup makes **only** EDHRec calls plus pure local computation. The thin live `/cards/named` fallback in `services/scryfall.py` (0.15s sleep, 429 backoff) only fires for a name absent from the bulk snapshot.

---

## Slept On Algorithm (reference)

Feature-lift model — Ferrone (2026), "Feature-Based Card Scoring for Commander
Recommendations". A *feature* is a card type, subtype, or oracle tag. We score how
much the commander over-uses each feature versus its color-identity baseline, then
sum those log-lifts across the features a candidate carries.

```
1. edhrec_cards = PyEDHRec cards for commander (each has inclusion + synergy)
2. For each card, features = {type:*, sub:*, otag:*} from type_line + bulk otags
3. Baseline trick: i_{c,B(X)} = edhrec_inclusion - edhrec_synergy   (no extra fetch;
   EDHRec synergy is defined as inclusion minus the color-identity baseline)
4. For each feature f over the recommended cards carrying f:
     P_X(f) = mean(edhrec_inclusion)            # commander's decks
     P_B(f) = mean(edhrec_inclusion - synergy)  # color-identity baseline
     lift[f] = log(P_X(f) / P_B(f))             # skip features with support < 3
     weight[f] = P_X(f) * lift[f]               # inclusion-weighted (KL term)
5. color_pool = all commander-legal cards in color identity (local bulk filter)
6. For each card in color_pool not in edhrec_cards (and not the commander itself):
     buzzword_score = sum(weight[f] for f in features(card) if f in weight)
7. Sort color_pool by buzzword_score desc, keep score > 0
8. Apply filters: inclusion cap, price cap, pauper toggle; return top N
```

Important — feature contributions are **inclusion-weighted** (`weight[f] = P_X(f) *
log(P_X(f)/P_B(f))`, a pointwise KL term). The raw log-lift is scale-invariant, so
without this weight a niche feature carried by a few low-inclusion cards counts as
much as a core theme — which made cards stacking many fringe tags (planeswalkers,
multi-subtype legends) run away with inflated, nonsensical scores. The weight makes
a feature matter only if the commander both over-uses it *and* actually plays it
often. `buzzword_score` (field name kept for template/JS compatibility) holds the
summed weighted lift; typical top scores are ~0.5–1.0, not 5–7.

---

## Testing

- No formal test suite required for this personal project.
- Manual smoke test: run `python app.py`, search for "Atraxa, Praetors' Voice", verify both sections render with data.

---

## Validation Sequence

Run after every implementation task:

```bash
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
```

Fix all errors before marking done.

---

## Memory System

Project-level persistent memory is stored in `memory/`. At the start of each session,
check `memory/MEMORY.md` for relevant prior context.

| File | Contains |
|---|---|
| `memory/MEMORY.md` | Index of all memory entries |
| `memory/user_profile.md` | Role and working preferences |
| `memory/feedback.md` | Corrections and confirmed approaches |
| `memory/project_context.md` | Decisions, goals, constraints, active work |
| `memory/references.md` | External systems — APIs, docs |

---

## Key Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | This file — agent rules |
| `CODEBASE-GUIDE.md` | Architecture deep-dive (load on demand) |
| `memory/MEMORY.md` | Persistent memory index |
| `.agents/PRDs/` | Generated PRDs |
| `.agents/plans/` | Generated implementation plans |

---

## Notes

- PyEDHRec 0.0.2 is an unofficial library. If it breaks, check its source and fall back to direct EDHRec JSON endpoints.
- Scryfall `search?q=otag:X+id<=COLOR` is the query pattern for color-identity + otag filtering.
- GitHub Pages serves from `/docs` on `master` branch — `export.py` must write there.
- The "Slept On" section is the core differentiator of this app. Keep its logic in `services/analysis.py` and well-commented.
- Personal use only — no auth, no user accounts, no scalability concerns.
