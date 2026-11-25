# Plan: M0-B — EDHRec/Archidekt drift and routing fixes

## Summary
Harden the EDHRec and Archidekt boundaries against the schema drift found by the
2026-11-25 audit + QA run, and fix the routing bugs it surfaced: unknown/renamed
EDHRec list tags, a silent-zero data contract, lossy slugs, DFC commanders from
Archidekt, Archidekt's first-category rule, input validation / error surfacing,
and a duplicate EDHRec fetch on tag-only views. No new cache layer, no route
restructure, no test suite (separate work packages).

## Metadata
| Field | Value |
|-------|-------|
| Type | BUG FIX |
| Complexity | MEDIUM |
| Branch | `m0/b-edhrec-archidekt-drift` (from origin/master) |
| Systems Affected | `services/edhrec.py`, `services/archidekt.py`, `app.py` (`index()`, `commander()`, `__main__` only), `templates/commander.html`, `templates/error.html`, `static/css/style.css` (banner rule next to `nav.tabs`) |
| Out of bounds | `services/bulk.py`, `services/scryfall.py`, `requirements.txt`, `templates/base.html`, end of `style.css`, top-of-file context processor in `app.py` (sibling work package) |

---

## Context Facts (verified live 2026-11-25)

- **EDHRec list tags now seen** (Ur-Dragon, Atraxa, Krenko, Thrasios+Tymna, and
  Ur-Dragon `/budget`, `/cedh`, `/dragons`): `newcards`, `topcards`,
  `highliftcards` (not on every page, e.g. absent for Atraxa), then the type lists
  `creatures`, `instants`, `sorceries`, `utilityartifacts`, `enchantments`,
  `battles`, `planeswalkers`, `utilitylands`, `manaartifacts`, `lands`.
  `highsynergycards` and `gamechangers` no longer appear.
- **Meta lists are now disjoint from the type lists.** 0/5 newcards, 0/10
  topcards, 0/10 highliftcards on Ur-Dragon also appear in a type list (same for
  Atraxa). The old comment "meta cardlists duplicate cards already present in the
  type categories" is false today: skipping them drops the ten most-played cards
  (`topcards`) from the scoring set and from their type groups.
- **New per-card field `lift`** (plus `trend_zscore`) on every cardview; keys are
  `id, image_version, lift, name, num_decks, potential_decks, sanitized, slug,
  synergy, trend_zscore, url`.
- A pairing fetched in the non-canonical order returns **200 with
  `{"redirect": "/commanders/<canonical>"}`** (no `container`), which
  `_fetch_json_dict` already treats as a failure; `resolve_pairing_slug` then tries
  the other order. Unknown slugs return **403**.
- **EDHRec slug rule** (confirmed on 20+ names): front face only, NFKD + drop
  combining marks, lowercase, `/` -> `-` (`SP//dr` -> `sp-dr-...`), drop every
  other non-`[a-z0-9 -]` character (so `H.E.R.B.I.E.` -> `herbie`,
  `U.S.Agent` -> `usagent`, `Ratonhnhaké꞉ton` -> `ratonhnhaketon`), whitespace /
  dash runs -> single `-`.
- **Archidekt** places a card in its FIRST category. Deck 1727139: 200 entries,
  any-category rule keeps 184, first-category rule keeps exactly 100.

---

## Tasks

### Task 1 — EDHRec list-tag drift (`services/edhrec.py`, `app.py`)
- Split tags into `_TYPE_TAGS` (type lists -> category = list header) and
  `_META_TAGS` (`newcards`, `topcards`, `highliftcards`, `highsynergycards`,
  `gamechangers`). `_FEATURED_TAGS` = `newcards`, `topcards`, `highliftcards`,
  `highsynergycards`, rendered in page order.
- `cards_from_data`: type lists first (category = header), then meta + unknown
  lists with `edhrec_category = ""`. Because the lists are disjoint, these cards now
  count toward scoring (they carry real inclusion/synergy). An unknown tag never
  becomes a category.
- New pure `assign_type_categories(cards)`: after Scryfall enrichment, put each
  uncategorised card in its type group from its front-face `type_line` (Creature >
  Planeswalker > Battle > Land > Instant > Sorcery > Artifact > Enchantment;
  `mana-rock*` otag -> Mana Artifacts, `utility-land` otag -> Utility Lands).
- Verify: Ur-Dragon EDHRec tab has no "High Lift Cards" category, shows a "High
  Lift Cards" featured row, Hellkite Courser appears under Creatures.

### Task 2 — Runtime contract check (`services/edhrec.py`, `app.py`, `commander.html`, `style.css`)
- Pure `contract_problems(data, cards)`: zero cards, < half with inclusion > 0,
  unknown list tags. Route logs each via `app.logger.error` and renders
  `data_warning` as a banner above the tabs (CSS next to `nav.tabs`).
- Guard `commander_info_from_data` (`.get`, return `None` + log on missing name /
  color identity); route shows an "unexpected format" error page instead of 500.
- Verify: banner absent on Atraxa; forced bad data (renamed `num_decks`, unknown
  tag, missing `card.name`) produces log + banner / error page, not 500.

### Task 3 — Slugs (`services/edhrec.py`)
- Rewrite `slugify` per the rule above; `resolve_pairing_slug` / `_scope_url`
  already call it.
- Verify: all six audit names + a sample of other accented/punctuated names and
  ordinary names resolve live (small, spaced sample).

### Task 4 — DFC commander from Archidekt
- `slugify` keeps only the face before `" // "` (not a bare `//`: `SP//dr`).
- Verify: deck 18289857 redirects to `/commander/esika-god-of-the-tree?deck=...`
  and renders.

### Task 5 — Archidekt first-category rule (`services/archidekt.py`)
- Keep a card iff it has no categories or its first category is included.
- Verify: deck 1727139 -> 100 card names.

### Task 6 — Validation and errors (`services/edhrec.py`, `app.py`, `error.html`)
- `?deck=` must be digits; `tag` / `bracket` must match `^[a-z0-9][a-z0-9-]{0,63}$`
  (checked in the route, which drops them and warns, and again in `_scope_url`).
- `get_commander_data` records the scope actually served; route warns via
  `data_warning` when it differs from the request (incl. bracket ignored because a
  tag holds EDHRec's single theme slot).
- Fetch errors classified `not_found` (4xx / missing container) vs `network`
  (connection, timeout, 5xx); the route shows a distinct 502 page for network.
- `error.html` wraps content in `.error-page`.
- `debug` from `FLASK_DEBUG` (default on, so `python app.py` is unchanged).
- Verify: bogus deck/tag values, an unfetchable tag, a nonsense slug, a simulated
  network failure, and the error page markup.

### Task 7 — Duplicate fetch (`app.py`)
- Reuse `display_data` for scoring when the served display scope already equals
  the scoring scope (`(tag, "")` or base).
- Verify: tag-only view issues one EDHRec request (log count), output unchanged.

## Validation (every task)
```
flake8 .
python -m py_compile app.py services/edhrec.py services/archidekt.py
```
Plus a real-app check on port 5002: Atraxa, The Ur-Dragon, Tymna + Thrasios,
the Archidekt repro decks, a nonsense slug.
