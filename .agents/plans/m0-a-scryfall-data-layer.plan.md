# Plan: M0-A — Scryfall data layer repair

## Summary
The local Scryfall bulk store (`services/bulk.py`) silently stopped refreshing:
Scryfall's `/bulk-data` listing dropped `download_uri` (the `.json` files now 404)
and only publishes `jsonl_download_uri` (gzip JSON-Lines). A fresh install ends up
"loaded" with empty indices. This package migrates the store to JSONL-gzip, makes
load/refresh failures visible (status + footer), cleans the candidate pool (meld
results, sticker sheets, basic lands), derives price/rarity facts across all paper
printings, makes the live `/cards/named` fallback polite (negative cache + time
budget), and tightens the commander/partner lists.

## Metadata
| Field | Value |
|-------|-------|
| Type | BUG FIX (data layer) |
| Complexity | MEDIUM |
| Work package | M0-A |
| Systems Affected | `services/bulk.py`, `services/scryfall.py`, `app.py` (context processor only), `templates/base.html`, `static/css/style.css` (appended footer style), `requirements.txt`, `CLAUDE.md` |

## Context Facts (verified 2026-11-25)
- Live `GET /bulk-data`: each entry has `type`, `updated_at`, `jsonl_download_uri`,
  `compressed_size`; no `download_uri`. `default_cards` ~81 MB gz, `oracle_tags`
  ~6 MB gz. Served as `Content-Type: application/gzip` (no `Content-Encoding`), so
  `requests` hands back the raw gzip bytes; store as `*.jsonl.gz` and decompress
  with `gzip.open(..., "rt")` line by line.
- `bulk.py` mutates live globals in place during a rebuild (`.clear()` then
  `.update()`), with no reader lock — readers can observe half-built indices.
- Out of bounds for this package: bodies of `index()` / `commander()` in `app.py`,
  `services/edhrec.py`, `services/archidekt.py`, `templates/commander.html`,
  `templates/error.html` (sibling work package).

## Tasks

### Task 1: JSONL-gzip bulk format, load status, atomic index swap
- `_BULK_FILES` -> `default-cards.jsonl.gz`, `oracle-tags.jsonl.gz`; download from
  `jsonl_download_uri`, verify byte count vs `Content-Length`, record Scryfall's
  `updated_at` in `cache/bulk-meta.json`; delete legacy `.json` files after a
  successful replacement.
- Parse with stdlib `gzip` + `json.loads` per line; drop `ijson` from
  `requirements.txt`.
- Build all indices into a `_Store` object in locals and publish it with one
  reference assignment; derived memos (commander names, partner pools, ancestor
  cache) live on the store so they can never mix snapshots.
- Status: `empty | loading | ready | error`, `last_refresh_failed`. A build that
  yields no cards/tags is an error and is never published. Failed first loads are
  retried at most every 5 minutes instead of on every request.
- **Verify:** delete nothing in main checkout; in the worktree run a fresh-install
  cold start (no `cache/`), record wall time + peak working set; compare against the
  old ijson parser run on an equivalent JSON-array file. Simulate a failed listing
  and confirm status `error` + store not marked loaded.

### Task 2: Data-age footer
- `bulk.snapshot_info()` (pure; never loads): `as_of`, `as_of_date`, `card_count`,
  `state`, `last_refresh_failed`, `age_days`, `warn`.
- `app.py`: one `@app.context_processor` right after `app = Flask(__name__)`.
- `base.html` footer line; `.data-age` / `.data-age.warn` appended to `style.css`.
- **Verify:** render pages on port 5001 in loading, ready, and forced-warn states.

### Task 3: Candidate-pool junk
- Meld results (`layout == "meld"` and the card's own `all_parts` entry is
  `component == "meld_result"`) and sticker sheets are marked
  `commander_legal = False` (they cannot be put in a deck), so they drop out of the
  pool, commander list, and partner pools while `card_record` still resolves them.
- `color_identity_pool` skips `Basic` supertype lands only.
- **Verify:** scratch script — Urza, Planeswalker / Brisela absent from pool and
  commander names; meld parts (Gisela, Bruna, Urza Lord Protector) present; no
  sticker sheets; no basics in pool; `card_record("Forest")` resolves.

### Task 4: Price / rarity across printings
- In the existing all-printings pass track per oracle id the min non-foil paper
  `prices.usd` (excluding memorabilia / gold-border / oversized) and `ever_common`.
  `price_usd` = that min; displayed printing (and its `rarity`) chosen exactly as
  before. Add `ever_common` to `scryfall._details_from_record` /
  `_empty_card_details` / live fallback; not wired into UI.
- **Verify:** scratch script — Mana Confluence, Boros Charm, Blasphemous Act have a
  price; counts of missing-price and common-mismatch before vs after.

### Task 5: Polite live fallback
- Negative cache (30 min TTL) for failed `/cards/named` lookups; per-request
  fallback budget (10 s) in `get_cards_collection`; `_get` never sleeps past the
  deadline.
- **Verify:** scratch script with fake names — second call is instant, first call
  is capped by the budget.

### Task 6: Commander list hygiene
- `commander_names()` requires `commander_legal`.
- `_can_be_commander`: front-face type line; legendary creature, legendary
  Vehicle/Spacecraft with printed P/T, "can be your commander", or Grist-style
  "isn't on the battlefield ... creature" text. Cross-check against Scryfall
  `is:commander`.
- `_partner_kind`: "Partner with X" -> only X; "Partner—Variant" pairs only with
  the same variant; Doctor's companion <-> Time Lord Doctor.
- **Verify:** scratch script — no "A-" names, Grist/Hearthhull present, Pir offers
  only Toothy, Doctor's companion offers Doctors.

### Task 7: Docs
- Update CLAUDE.md "Scryfall Bulk Data" for format and sizes.

## Validation (every task)
```
flake8 .
python -m py_compile app.py services/bulk.py services/scryfall.py
```
(Using the main checkout's `.venv` interpreter, cwd = worktree.)
