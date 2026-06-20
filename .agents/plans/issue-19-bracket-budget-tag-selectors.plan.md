# Plan: Bracket / budget / tag selectors with tag-aware Slept On rescoring

## Summary
Add three selectors to the commander page — **tag** (theme), **budget**, and
**bracket** — that re-scope the EDHRec view by re-rendering the page with query
params (`/commander/<slug>?tag=&budget=&bracket=`). EDHRec serves each scope as a
sibling JSON page under the stable endpoint #15 already uses, so all fetching stays
in `services/edhrec.py` and all scoring stays pure in `services/analysis.py`. Per the
product decision: **only a tag recomputes the Slept On feature weights** (rescoring);
**budget and bracket are display scopes** that change which EDHRec cards are shown
while the Buzzword Scores stay anchored to the default (no-tag) all-cards baseline. A
small note in the UI makes the scope-vs-score distinction explicit. Selector options
come from EDHRec's per-commander `taglinks` (183 themes) for tags, with static
fallback sets for budget (Any/Budget/Expensive) and bracket (Any/cEDH — EDHRec's
numbered brackets aren't exposed via the static JSON).

## User Story
As a Brewer, I want to filter the page by bracket and budget and pick a theme/tag, so
that I can browse the scope I care about and get recommendations tuned to my build.

## Metadata
| Field | Value |
|-------|-------|
| Type | ENHANCEMENT |
| Complexity | HIGH |
| GitHub Issue | #19 |
| Systems Affected | `services/edhrec.py`, `app.py` (commander route), `templates/commander.html`, `static/js/filters.js` |
| **Blocked by** | **#15** (`get_commander_data`, `cards_from_data`, `inclusion_index_from_data`, `commander_info_from_data`, `_card_from_cardview`). Integrates with #17 (featured sections re-scope automatically). |

> **Sequencing:** Implement after #15 (and ideally #17). This plan extends
> `edhrec.get_commander_data` to take scope params and reads them in the route.

---

## Spike Findings (verified live, 2026-06-20)

EDHRec scope pages under `https://json.edhrec.com/pages/commanders/<slug>...`:

| Scope | URL | Result |
|-------|-----|--------|
| Base | `/<slug>.json` | 200 (default, ~292 cards) |
| Tag | `/<slug>/infect.json` | 200, header "… - Infect" |
| Budget | `/<slug>/budget.json` | 200, header "… - Budget" |
| Expensive | `/<slug>/expensive.json` | 200, header "… - Expensive" |
| Tag + budget | `/<slug>/infect/budget.json` | 200, header "… - Budget Infect" |
| cEDH | `/<slug>/cedh.json` | 200, header "… - cEDH" |
| `bracket-1` / `bracket-2` | `/<slug>/bracket-1.json` | **403 — not exposed** |

- **URL model** (matches pyedhrec `pyedhrec.py:82-110 _build_nextjs_uri`): `<slug>` +
  **one** optional theme slug (a tag **or** `cedh` — single slot) + optional
  `/budget` | `/expensive` tier + `.json`.
- **Tag options**: `data["panels"]["taglinks"]` = list of `{count, slug, value}` (183
  for Atraxa), e.g. `{"slug":"infect","value":"Infect","count":5145}`. Sort by `count`
  desc for a useful menu.
- **Bracket**: EDHRec's numbered game brackets are NOT available via the static JSON
  (403). Per the AC's "fallback to a known static set", the bracket selector offers the
  power scope that *is* exposed: `Any` / `cEDH`.
- **Conflict**: a tag and `cedh` both occupy the single theme slot, so they can't both
  be in one URL → **precedence: tag > bracket** (tag drives rescoring). Budget is a
  separate tier and composes with either.

---

## Design

### Query params (route reads `request.args`)
- `tag` — a theme slug from `taglinks` (or empty).
- `budget` — `""` | `budget` | `expensive`.
- `bracket` — `""` | `cedh`.

### URL composition (in `edhrec.get_commander_data`)
`<slug>` + `/<theme>` (where `theme = tag or bracket`, tag winning) + `/<budget>` (if
`budget in {budget, expensive}`) + `.json`. **Graceful fallback**: if the composed URL
returns non-200, retry dropping the least-important segment in order
(bracket → budget) until a 200 (ultimately the base page), so no selector combo can
500 the route.

### Two views, deduped (the crux)
- **scoring view** = base, unless a **tag** is set → tag-only view (`tag`, no
  budget/bracket). Feature weights are computed from this view → satisfies "tag
  rescores; budget/bracket keep scoring fixed".
- **display view** = the fully-composed scope (tag+bracket+budget) → drives the EDHRec
  tab cards, featured sections (#17), the inclusion cross-ref, and the Slept On
  exclusion set.
- Fetch each **unique** param-set once (when scoring view == display view, e.g. no
  selection or tag-only with no budget, it's a single fetch).

This is ≤ 2 EDHRec fetches per request — acceptable for a local personal app, and the
bulk Scryfall enrichment is unchanged.

---

## Patterns to Follow

### Stable scope fetch + error contract (extend this)
```python
# SOURCE: services/edhrec.py:16-34 (get_commander_info) — fetch/try/except/logger.error
url = f"{EDHREC_JSON_BASE}/{slug}.json"
resp = requests.get(url, headers=HEADERS, timeout=10)
resp.raise_for_status()
...
except Exception as e:
    logger.error("...failed for %r: %s", slug, e)
    return None
```

### pyedhrec URL composition (reference only — we use the stable pages endpoint)
```python
# SOURCE: .venv/.../pyedhrec/pyedhrec.py:82-110 (_build_nextjs_uri)
# uri = base/<slug>[/<theme>][/budget|expensive].json
```

### Route reads request + renders (extend)
```python
# SOURCE: app.py:16-22 (request.form) and app.py:33-92 (commander route, render_template kwargs)
tag = request.args.get("tag", "")
```

### Existing on-page controls + JS wiring
```html
<!-- SOURCE: templates/commander.html:7-10 (#controls block) -->
<div id="controls"> ... <input id="price-cap"> ... </div>
```
```javascript
// SOURCE: static/js/filters.js:1-10, 86-90 (grab elements, addEventListener)
priceCapInput.addEventListener('input', applyFilters);
```

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `services/edhrec.py` | UPDATE | Scope params + URL composition w/ graceful fallback; `available_tags_from_data`; budget/bracket option constants. |
| `app.py` | UPDATE | Read `tag/budget/bracket`; resolve scoring vs display views; compute weights from scoring view; pass selectors + selected values. |
| `templates/commander.html` | UPDATE | Three `<select>` controls + scope-vs-score note; preserve selected values. |
| `static/js/filters.js` | UPDATE | On selector change, navigate to the route with updated query params. |

No new dependencies.

---

## Tasks

Execute in order.

### Task 1: Scope-aware fetch + tag options in edhrec.py
- **File**: `services/edhrec.py`
- **Action**: UPDATE
- **Implement**:
  1. Add option constants:
     ```python
     BUDGET_OPTIONS = ("", "budget", "expensive")   # "" = Any
     BRACKET_OPTIONS = ("", "cedh")                  # "" = Any; numbered brackets not in static JSON
     ```
  2. Add a private URL builder:
     ```python
     def _scope_url(slug: str, theme: str = "", budget: str = "") -> str:
         path = slugify(slug)
         if theme:
             path += f"/{theme}"
         if budget in ("budget", "expensive"):
             path += f"/{budget}"
         return f"{EDHREC_JSON_BASE}/{path}.json"
     ```
  3. Extend the #15 fetch to accept scope + fall back gracefully. Signature:
     ```python
     def get_commander_data(slug, tag="", budget="", bracket=""):
         """
         Fetch the EDHRec page json_dict for a commander scope. `theme` = tag or
         bracket (tag wins; EDHRec allows one theme slug). On non-200/parse error,
         retry dropping bracket, then budget, then base, so an unsupported combo
         degrades instead of failing.
         """
         theme = tag or bracket
         # candidate (theme, budget) tuples, most- to least-specific
         attempts = [(theme, budget)]
         if bracket and tag:           # both set -> also try tag-only
             attempts.append((tag, budget))
         if budget:
             attempts.append((theme, ""))
         attempts.append(("", ""))     # base, last resort
         for th, bg in dict.fromkeys(attempts):   # dedupe, keep order
             data = _fetch_json_dict(_scope_url(slug, th, bg))
             if data:
                 return data
         return None
     ```
     where `_fetch_json_dict(url)` is the extracted try/except GET returning
     `resp.json()["container"]["json_dict"]` or `None` (mirror `get_commander_info`).
  4. Add `available_tags_from_data(data) -> list[dict]`: read
     `data.get("panels", {}).get("taglinks", [])`, return `[{"slug","value","count"}]`
     sorted by `count` desc. Return `[]` if absent (graceful).
  Keep `cards_from_data`, `inclusion_index_from_data`, `commander_info_from_data`,
  `featured_sections_from_data` (#15/#17) unchanged — they take `data` and are
  scope-agnostic.
- **Mirror**: `services/edhrec.py:16-34` (fetch), pyedhrec `_build_nextjs_uri`.
- **Validate**: `flake8 services/edhrec.py && python -m py_compile services/edhrec.py`

### Task 2: Resolve scoring vs display views in the route
- **File**: `app.py`
- **Action**: UPDATE
- **Implement** (in `commander(slug)`, post-#15/#17):
  1. Read params:
     ```python
     tag = request.args.get("tag", "")
     budget = request.args.get("budget", "")
     bracket = request.args.get("bracket", "")
     ```
  2. **Display view** (fully scoped): `display_data = edhrec.get_commander_data(slug, tag=tag, budget=budget, bracket=bracket)`. 404 via `error.html` if falsy.
     Derive `info`, `edhrec_cards`, `featured`, `incl_index`, and `available_tags`
     from `display_data` (as #15/#17 do).
  3. **Scoring view**: if `tag`, fetch the tag-only view for weights; else reuse the
     display data when no tag (the base view *is* the scoring view) — but note budget/
     bracket must NOT influence weights:
     ```python
     if tag:
         scoring_data = edhrec.get_commander_data(slug, tag=tag)   # tag only, no budget/bracket
     elif budget or bracket:
         scoring_data = edhrec.get_commander_data(slug)            # base baseline
     else:
         scoring_data = display_data                               # already the base
     scoring_cards = edhrec.cards_from_data(scoring_data)
     ```
     Enrich `scoring_cards` minimally only as needed for `compute_feature_stats`
     (it needs `edhrec_inclusion`, `edhrec_synergy`, `type_line`, `otags`). Reuse the
     existing Scryfall enrichment helper; combine names with the display enrichment to
     keep it to one `get_cards_collection` call (mirror #17's combined-names approach).
  4. Compute weights from the scoring view:
     `feature_stats = analysis.compute_feature_stats(scoring_cards)`;
     `weights = {s["feature"]: s["weight"] for s in feature_stats}`.
  5. Everything else (color pool, inclusion join from `incl_index` of the **display**
     view, `score_cards`, featured display-scoring) stays as in #15/#17, now using
     `weights`.
  6. Pass to template: `selected_tag=tag, selected_budget=budget,
     selected_bracket=bracket, available_tags=available_tags,
     budget_options=edhrec.BUDGET_OPTIONS, bracket_options=edhrec.BRACKET_OPTIONS`.
- **Mirror**: `app.py:33-92` (route flow), #17 combined-names enrichment.
- **Validate**: `flake8 app.py && python -m py_compile app.py`

### Task 3: Selector controls + scope note in the template
- **File**: `templates/commander.html`
- **Action**: UPDATE
- **Implement**: In the `#controls` block (`:7-10`), add three labelled `<select>`s
  preserving the current selection, plus a short scope-vs-score note:
  ```jinja
  <label>Theme:
    <select id="tag-select" data-param="tag">
      <option value="">All cards</option>
      {% for t in available_tags %}
      <option value="{{ t.slug }}" {{ 'selected' if t.slug == selected_tag }}>{{ t.value }} ({{ t.count }})</option>
      {% endfor %}
    </select>
  </label>
  <label>Budget:
    <select id="budget-select" data-param="budget">
      <option value="">Any</option>
      <option value="budget"    {{ 'selected' if selected_budget == 'budget' }}>Budget</option>
      <option value="expensive" {{ 'selected' if selected_budget == 'expensive' }}>Expensive</option>
    </select>
  </label>
  <label>Bracket:
    <select id="bracket-select" data-param="bracket">
      <option value="">Any</option>
      <option value="cedh" {{ 'selected' if selected_bracket == 'cedh' }}>cEDH</option>
    </select>
  </label>
  <p class="scope-note">Only <strong>Theme</strong> re-scores Slept On; Budget &amp; Bracket re-scope the displayed cards only.</p>
  ```
  Keep the price-cap and pauper controls intact.
- **Mirror**: `templates/commander.html:7-10`.
- **Validate**: page renders (Task 5).

### Task 4: Navigate on selector change
- **File**: `static/js/filters.js`
- **Action**: UPDATE
- **Implement**: Add a block (after the existing listeners, before/around `:86-90`)
  that, for each `select[data-param]`, on `change` updates that query param on the
  current URL and navigates (full reload re-runs the server scope logic):
  ```javascript
  document.querySelectorAll('select[data-param]').forEach(sel => {
    sel.addEventListener('change', () => {
      const url = new URL(window.location.href);
      if (sel.value) url.searchParams.set(sel.dataset.param, sel.value);
      else url.searchParams.delete(sel.dataset.param);
      window.location.assign(url.toString());
    });
  });
  ```
  Guard remains the existing `if (!nSlider) return;` early-out (selectors only exist on
  the commander page). No change to price/pauper/N/inclusion client filters.
- **Mirror**: `static/js/filters.js:86-90` (listener attach), `:9-10` (guard).
- **Validate**: page interaction (Task 5).

### Task 5: Manual smoke test
- **File**: n/a
- **Action**: verify
- **Implement**:
  1. `python app.py`, open `/commander/atraxa-praetors-voice`.
  2. **Tag**: pick a theme (e.g. "Infect") → URL gets `?tag=infect`, EDHRec tab reflects
     the theme, and **Slept On reorders** (weights changed). Note the Diagnostics table
     also changes.
  3. **Budget**: set Budget → URL gets `&budget=budget`, EDHRec cards change to the
     budget set, but **Slept On Buzzword Scores are unchanged** vs. the no-budget view
     (spot-check a card's score).
  4. **Bracket**: set cEDH → EDHRec re-scopes; scores unchanged. With a tag also set,
     confirm no error (tag precedence / graceful fallback).
  5. Confirm selected values persist in the dropdowns after reload, and clearing back to
     "All cards / Any" returns to the base view.
- **Validate**: visual; tag reorders Slept On, budget/bracket don't move scores, no 500s.

---

## Validation Sequence

```bash
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py
python app.py   # exercise the three selectors on /commander/atraxa-praetors-voice
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Implemented before #15 → missing `get_commander_data`/extractors | Marked **Blocked by #15**; verify symbols exist first. |
| Unsupported scope combo (e.g. tag+cedh, or a tag with no budget page) returns non-200 | `get_commander_data` retries dropping bracket→budget→base; never 500s. |
| Budget/bracket accidentally change scores | Weights come strictly from the **scoring view** (tag-only or base); budget/bracket feed only the **display view**. Task 5 step 3 verifies. |
| Two EDHRec fetches add latency | Only when budget/bracket combined with (or without) a tag; deduped to ≤2. Acceptable for local use; bulk Scryfall data is already warm. |
| `taglinks` missing for some commander | `available_tags_from_data` returns `[]` → the theme select shows only "All cards" (graceful). Budget/bracket use static fallback sets per AC. |
| Numbered EDHRec brackets expected but unavailable | Documented: static JSON 403s on `bracket-N`; bracket selector offers the exposed `cEDH` scope (AC's static-fallback clause). Numbered brackets are a future item. |
| Full reload feels heavy vs. AJAX | Server reload keeps all logic in the service/analysis layers per CLAUDE.md and is far simpler; AJAX rescore is a deferred enhancement. |

---

## Out of Scope (per issue)
- Bracket/budget **rescoring** (they stay display-only).
- Multi-tag / arbitrary tag combinations (single tag only).
- EDHRec's numbered game brackets (not exposed by the static endpoint).
- AJAX/partial re-render (full server reload is used).

---

## Acceptance Criteria

- [ ] Tag, budget, and bracket selectors on the commander page, populated from EDHRec
      (`taglinks`) with static fallback sets for budget/bracket.
- [ ] Selecting a **tag** refetches that view and recomputes Slept On weights/order.
- [ ] Selecting **budget/bracket** changes displayed cards but leaves Buzzword Scores
      unchanged.
- [ ] A visible note states only the theme re-scores.
- [ ] Route accepts `tag/budget/bracket` params; fetching in `edhrec.py`, scoring pure
      in `analysis.py`.
- [ ] `flake8 .` clean; `py_compile` clean.
- [ ] Smoke test: tag reorders Slept On; budget filters cards without moving scores.
- [ ] Follows CLAUDE.md layering.
- [ ] GitHub Issue #19 criteria satisfied.
```
