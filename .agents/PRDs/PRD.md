# Product Requirements Document
# MTG EDH Sleeper Picks

**Version:** 1.0  
**Date:** 2026-06-19  
**Status:** Draft

---

## 1. Executive Summary

MTG EDH Sleeper Picks is a locally hosted web application for Magic: The Gathering players building Commander (EDH) decks. It replicates the functionality of the EDHRec commander page — showing which cards are most commonly included in decks built around a given commander — while adding a mathematically derived "Slept On" section that surfaces underplayed cards with high functional synergy.

The core insight is that EDHRec's inclusion metrics reflect what players *already* build, not what might be *optimal*. The app scores every card in the commander's color identity with a **feature-lift model** (Ferrone, 2026): for each card characteristic — type, subtype, or Scryfall oracle tag — it measures how much the commander's decks over-use that characteristic relative to the color-identity baseline (`lift = log(P_X / P_base)`), weights each lift by how often the commander actually plays cards carrying it (`weight = P_X × lift`, a pointwise KL term), and sums those weights across a candidate card's characteristics. This surfaces underplayed cards that "do the same things" as the commander's signature themes but fly under the radar due to lower name recognition, recent printing, or format novelty — with no cold-start gap, since the score is computable even for brand-new cards with no deck history.

The MVP is a Flask-based local web app with a static HTML export pathway for optional GitHub Pages hosting. It is a single-user personal tool with no authentication, no database, and no scalability requirements.

---

## 2. Mission

**Mission Statement:** Give Commander players a fast, data-driven way to find the hidden gems their opponents aren't running — right on their own machine.

**Core Principles:**
1. **Signal over noise** — surface the cards that matter via math, not hype.
2. **Simple by design** — personal tool; no auth, no backend complexity, no cloud dependencies.
3. **Respect the data sources** — respect Scryfall and EDHRec rate limits and terms.
4. **Transparency** — every "Slept On" card should have a visible score so the user understands why it appeared.
5. **Speed to insight** — from commander name to full analysis in one page load (or close to it).

---

## 3. Target Users

### Primary Persona: The Enthusiast Deckbuilder
- **Who:** A single Magic: The Gathering player (the app author) who builds Commander decks regularly.
- **Technical comfort:** Comfortable running Python scripts locally, familiar with pip and virtual environments, can read basic Flask output in a terminal.
- **Key needs:**
  - Quickly evaluate a new commander without manually sifting through hundreds of EDHRec cards.
  - Find non-obvious cards that fit the deck's game plan (synergy) but aren't overplayed.
  - Filter by budget (price cap) and format constraints (pauper toggle for budget/commons-only builds).
- **Pain points:**
  - EDHRec shows *popular* cards, not necessarily *optimal* ones for a given strategy.
  - Manually cross-referencing oracle tags and prices across multiple sites is tedious.
  - Budget constraints make rarity/price filtering essential.

---

## 4. MVP Scope

### In Scope
- [ ] **Landing page** with a commander name search bar
- [ ] **Commander page** displaying EDHRec recommended cards (mirroring standard EDHRec layout, grouped by category)
- [ ] **Per-card data:** card image, name, EDHRec synergy %, EDHRec inclusion %, TCGPlayer price (via Scryfall), rarity
- [ ] **Slept On section:** top-N cards by feature-lift score, excluding the EDHRec list and the commander itself
- [ ] **Score computation:** inclusion-weighted feature-lift model over card type/subtype/oracle-tag characteristics (`weight = P_X × log(P_X / P_base)`)
- [ ] **Slept On controls:**
  - Slider for N (1–100, default 50)
  - Inclusion cap slider (0–100%, default 10%) — excludes cards already frequently used
- [ ] **Tabbed layout:** Slept On / EDHRec / Diagnostics
- [ ] **Diagnostics tab:** per-characteristic table showing support, P_X, P_base, lift, and weight — so the user can see exactly why cards score the way they do
- [ ] **Click-to-copy:** clicking any card copies its name to the clipboard (with a toast confirmation)
- [ ] **Filters (both sections):**
  - Price cap input (hide cards above $X.XX)
  - Pauper toggle (show only common-rarity cards)
- [ ] **Local Scryfall bulk store:** `default_cards` + `oracle_tags` cached to `cache/`, refreshed every 24h; serves attributes/tags/color-pool with no per-request HTTP. Picks each card's cleanest standard printing (no art-series/borderless/full-art)
- [ ] **Static HTML export** (`export.py` → `/docs` folder) for GitHub Pages
- [ ] Scryfall-sourced prices (no separate API key required)

### Out of Scope (Deferred)
- [ ] User accounts or saved deck lists
- [ ] Database / persistent storage of analysis results
- [ ] Deck import/export (Moxfield, Archidekt, etc.)
- [ ] Multiple commander (partner/background) support
- [ ] Card comparison view or side-by-side diffing
- [ ] Full EDHRec category breakdowns with collapsible sections
- [ ] Mobile-optimized layout
- [ ] Automated/scheduled data refresh
- [ ] Multi-user deployment or cloud hosting beyond GitHub Pages static export
- [ ] TCGPlayer direct API integration

---

## 5. User Stories

**US-1: Commander Search**
As a deckbuilder, I want to type a commander's name into a search bar and navigate to their analysis page, so that I can start evaluating card choices without leaving the app.
*Example: I type "Atraxa, Praetors' Voice" and press Enter. The app fetches EDHRec data and shows a loading state before rendering the commander page.*

**US-2: EDHRec Card List**
As a deckbuilder, I want to see the standard EDHRec recommended cards for my commander — with synergy score, inclusion rate, price, and rarity — so that I have the same baseline information EDHRec provides.
*Example: The page shows "Sol Ring — 99% inclusion, +5% synergy, $1.20, Uncommon" with its card art.*

**US-3: Slept On Discovery**
As a deckbuilder, I want to see a "Slept On" section of underplayed cards that share functional DNA with the recommended list, so that I can find non-obvious includes my opponents won't expect.
*Example: A card like "Exotic Orchard" appears in Slept On for a 4-color commander because its otags overlap heavily with frequently recommended mana-fixing cards.*

**US-4: Buzzword Score Transparency**
As a deckbuilder, I want to see each Slept On card's Buzzword Score, so that I understand *why* it was surfaced and can evaluate its relevance myself.
*Example: Hovering or looking at a card shows "Buzzword Score: 14.3 (ramp: 6.1, color-fix: 5.2, enters-tapped: 3.0)".*

**US-5: Adjust Slept On Size**
As a deckbuilder, I want to adjust how many Slept On cards are shown via a slider, so that I can get a quick top-10 or dig deep into top-100.
*Example: I drag the slider from 50 to 20 and the list instantly shrinks to the top 20 cards.*

**US-6: Inclusion Cap Filter**
As a deckbuilder, I want to set an inclusion cap so that widely played cards (e.g., 40% inclusion) don't appear in the Slept On section, so that the section stays focused on genuinely underplayed picks.
*Example: I set the cap to 5% so only truly obscure cards appear.*

**US-7: Budget Filter**
As a deckbuilder building on a budget, I want to set a price cap so that expensive cards are hidden from both sections, so that every visible card is within my budget.
*Example: I set $2.00 as the max price and cards like "Demonic Tutor" disappear from view.*

**US-8: Pauper Toggle**
As a deckbuilder doing a pauper/commons-only build, I want a toggle that instantly hides all non-common cards, so that I can evaluate the commander in a budget pauper context.
*Example: I flip the Pauper switch and 90% of cards disappear, leaving only commons.*

**US-9: Click to Copy Card Name**
As a deckbuilder, I want to click a card to copy its name to my clipboard, so that I can quickly paste it into my deck builder (Moxfield/Archidekt) without retyping.
*Example: I click "Pith Driller" in the Slept On grid, a "Copied" toast appears, and I paste the name straight into my deck list.*

**US-10: Diagnostics Transparency**
As a deckbuilder, I want a Diagnostics tab showing the lift and weight of each card characteristic, so that I understand which types/subtypes/oracle tags are driving the Slept On scores and can trust (or question) the results.
*Example: I open Diagnostics for Atraxa and see `otag:synergy-proliferate` has a high weight, confirming the section is rewarding the deck's real theme.*

---

## 6. Core Architecture & Patterns

### High-Level Approach
Three-layer separation: Flask routes call service functions; service functions return plain Python dicts/lists; Jinja2 templates consume those dicts for rendering. No business logic in routes or templates.

### Directory Structure
```
mtg_edh_sleeper_picks/
├── app.py                    # Flask routes — thin, calls services only
├── services/
│   ├── edhrec.py             # PyEDHRec / EDHRec JSON → structured card list (inclusion + synergy)
│   ├── bulk.py               # Local Scryfall bulk store (default_cards + oracle_tags), printing selection
│   ├── scryfall.py           # Card details / color-identity pool served from bulk; thin live fallback
│   └── analysis.py           # Feature-lift scoring — pure functions, no I/O
├── templates/
│   ├── base.html             # Shared layout, nav, CSS/JS includes
│   ├── index.html            # Landing page: search bar
│   └── commander.html        # Commander page: EDHRec list + Slept On + filters
├── static/
│   ├── css/style.css         # Styles
│   └── js/filters.js         # Client-side filter logic (price cap, pauper, N slider)
├── export.py                 # Static site generator → writes /docs for GitHub Pages
├── requirements.txt
└── memory/                   # Agent persistent memory (do not delete)
```

### Key Design Patterns
- **Service layer:** All external API calls isolated in `services/`. Routes never call Scryfall or PyEDHRec directly.
- **Pure analysis:** `services/analysis.py` functions take lists and dicts as input, return scored lists. Zero I/O.
- **Client-side filtering:** Price cap, pauper toggle, and N slider operate on already-rendered HTML via `filters.js` — no server round-trip needed per filter change.
- **In-memory cache:** Scryfall results cached in a module-level dict for the duration of a single request. No disk persistence.

### Feature-Lift Scoring Algorithm (Ferrone, 2026)
```
1. edhrec_cards = EDHRec commander page (each card has inclusion i_{c,X} and synergy)
2. features(card) = {type:*, sub:*} from Scryfall type_line  ∪  {otag:*} from oracle tags
3. Baseline (no extra fetch): i_{c,B(X)} = inclusion - synergy
       (EDHRec synergy is DEFINED as inclusion minus color-identity baseline)
4. For each feature f, over the recommended cards carrying f:
       P_X(f)    = mean(i_{c,X})            # commander's decks
       P_base(f) = mean(i_{c,B(X)})         # color-identity baseline
       lift(f)   = log(P_X(f) / P_base(f))  # drop features with support < 3
       weight(f) = P_X(f) * lift(f)         # inclusion-weighted (pointwise KL term)
5. color_pool = commander-legal cards in color identity (local bulk filter)
6. For each card in color_pool NOT in edhrec_cards and NOT the commander:
       buzzword_score = sum(weight[f] for f in features(card) if f in weight)
7. Sort descending by buzzword_score; keep score > 0
8. Apply inclusion cap, price cap, pauper toggle (client-side for instant UX)
9. Return top N
```
> The inclusion weighting is load-bearing: the raw log-lift is scale-invariant, so
> without it cards stacking many fringe characteristics (e.g. planeswalkers with
> dozens of loyalty-ability tags) accumulate inflated, nonsensical scores. `weight(f)`
> makes a characteristic count only if the commander both over-uses it *and* plays it
> often. The `buzzword_score` field name is retained for template/JS compatibility.

---

## 7. Technology Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Runtime | Python | 3.12 | Already installed |
| Web framework | Flask | 3.x | Routing + dev server |
| Templating | Jinja2 | bundled | Included with Flask |
| EDHRec data | pyedhrec | 0.0.2 | Unofficial library; may need fallback to raw JSON endpoints |
| Card data & prices | Scryfall bulk data | — | `default_cards` + `oracle_tags` cached locally; `prices.usd` = TCGPlayer price; no API key |
| Bulk parsing | ijson | 3.2+ | Streams the ~547 MB `default_cards` file to bound memory |
| Static export | Frozen-Flask or custom | latest | Renders templates to `/docs` for GitHub Pages |
| Frontend interaction | Vanilla JS | ES6 | No framework; filters.js (filters + tabs + click-to-copy) |
| Linting | flake8 | latest | Enforced before every commit |
| Formatting | black | latest | Auto-format |

**> Assumption:** pyedhrec 0.0.2 returns at minimum: card name, EDHRec synergy score, inclusion percentage, and card category. If it breaks or is insufficient, we fall back to scraping EDHRec's JSON API directly.

---

## 8. Security & Configuration

### Auth
- None. Single-user local tool. No login, no sessions.

### Environment Variables
- None required for MVP. All API calls are to public endpoints (Scryfall, EDHRec).
- `> Assumption:` If PyEDHRec or EDHRec requires any key in the future, it will be added via a `.env` file with `python-dotenv`.

### Security Scope
- **In scope:** Basic input sanitization on commander name search (no shell injection risk since we're passing to a library, but validate non-empty, strip whitespace).
- **Out of scope:** XSS hardening, CSRF tokens, rate limiting, HTTPS (localhost only).

---

## 9. Success Criteria

### MVP Success Definition
The app is successful when: a user can search for any legal Commander, see all standard EDHRec recommended cards with prices and rarities, and see a "Slept On" section with scored, filterable underplayed picks — all in a single browser tab running on localhost.

### Functional Requirements
- [ ] Commander search returns results for any commander legal in the format
- [ ] EDHRec card list renders with image, name, synergy %, inclusion %, price, rarity
- [ ] Slept On cards are distinct from EDHRec list (no duplicates)
- [ ] Buzzword Score is visible per card in Slept On
- [ ] N slider updates Slept On list without page reload
- [ ] Inclusion cap slider updates Slept On list without page reload
- [ ] Price cap hides cards above the threshold in both sections
- [ ] Pauper toggle hides non-common cards in both sections
- [ ] `export.py` produces valid static HTML in `/docs` that renders correctly when opened in a browser
- [ ] Scryfall requests stay within rate limits (≤10 req/sec)

### Quality Indicators
- `flake8 .` passes with zero errors
- No unhandled exceptions on valid commander names
- Page renders in under 30 seconds for a typical commander (network-dependent)

---

## 10. Implementation Phases

### Phase 1: Foundation & Data Pipeline
**Goal:** Get data flowing from EDHRec and Scryfall to Python objects.

**Deliverables:**
- [ ] `requirements.txt` with all dependencies
- [ ] `services/edhrec.py` — fetch and parse commander card list via PyEDHRec
- [ ] `services/scryfall.py` — fetch otags, price, rarity, image URI per card; color identity search
- [ ] CLI smoke test: `python -c "from services import edhrec, scryfall; ..."` prints card data

**Validation:** Running the smoke test for "Atraxa, Praetors' Voice" returns ≥50 cards with names, synergy scores, and otags.

---

### Phase 2: Buzzword Score Engine
**Goal:** Implement the TF analysis and Slept On card ranking.

**Deliverables:**
- [ ] `services/analysis.py` — `compute_tf(edhrec_cards)` and `score_color_pool(color_pool, tf_dict)`
- [ ] End-to-end test: given Atraxa, print top 20 Slept On cards with scores to stdout
- [ ] Verify no EDHRec cards appear in Slept On output

**Validation:** Top Slept On cards have visible functional overlap with the EDHRec set (manual review). Scores are non-zero.

---

### Phase 3: Flask UI
**Goal:** Full web interface — search, commander page, both sections, all filters.

**Deliverables:**
- [ ] `app.py` with `/` (search) and `/commander/<slug>` routes
- [ ] `templates/base.html`, `templates/index.html`, `templates/commander.html`
- [ ] Card display component: image, name, synergy %, inclusion %, price, rarity, Buzzword Score (Slept On only)
- [ ] `static/js/filters.js` — N slider, inclusion cap slider, price cap input, pauper toggle
- [ ] `static/css/style.css` — clean, readable layout; no framework required
- [ ] `flake8 .` passes

**Validation:** Browse to `localhost:5000`, search "Atraxa", verify both sections render with working filters.

---

### Phase 4: Static Export
**Goal:** Produce a deployable static site for GitHub Pages.

**Deliverables:**
- [ ] `export.py` — renders commander pages to `/docs/*.html`
- [ ] `/docs/index.html` — static landing page (search becomes a dropdown of pre-generated commanders, or a JS-only filter on a list)
- [ ] GitHub Pages serves `/docs` on `master` branch
- [ ] README with local run instructions and GitHub Pages setup steps

**Validation:** Open `/docs/index.html` in a browser (no server). Slept On filters still function via client-side JS. Cards display correctly.

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **PyEDHRec 0.0.2 breaks or returns incomplete data** | Medium | High | Inspect library source; fall back to direct EDHRec JSON API endpoints (`https://json.edhrec.com/pages/commanders/...`). Document fallback in `services/edhrec.py`. |
| **Scryfall color identity search returns too many cards (10k+), making scoring slow** | Medium | Medium | Paginate Scryfall search; process in batches. Consider limiting to cards with at least one matching otag using Scryfall's `otag:` query syntax to reduce the pool before scoring. |
| **Scryfall rate limit (10 req/sec) causes timeouts on large card pools** | Medium | Medium | Add `time.sleep(0.1)` between card-level requests. Cache otag results in module dict to avoid re-fetching within the same request. |
| **GitHub Pages static export loses JS filter interactivity** | Low | Medium | All filters implemented in `filters.js` operating on rendered HTML — no server needed. Test static pages in a browser before declaring Phase 4 complete. |
| **PyEDHRec synergy scores are unavailable or in unexpected format** | Low | Medium | If synergy is missing, fall back to using inclusion % as the TF weight. Document the fallback in `analysis.py`. |

---

## 12. Future Considerations

- **Partner commanders:** Support two-commander pairings (background, partner with, friends forever).
- **Deck list import:** Paste a current deck list; exclude already-owned cards from both sections.
- **Otag breakdown tooltip:** Show which otags contributed to a card's Buzzword Score on hover.
- **Category grouping in Slept On:** Group Slept On cards by their highest-contributing otag category.
- **Pre-built commander cache:** Export analysis for a curated list of commanders so GitHub Pages users get instant results without re-running locally.
- **Price history:** Track price changes over time using Scryfall's bulk data download.
- **Moxfield / Archidekt export:** One-click export of the Slept On list to a deck builder.
- **Commander search autocomplete:** Use Scryfall's `/cards/autocomplete` endpoint for live suggestions as the user types.
