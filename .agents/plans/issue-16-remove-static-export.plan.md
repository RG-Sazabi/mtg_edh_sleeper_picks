# Plan: Remove static export pipeline (export.py, docs/, frozen-flask) and update docs

## Summary
GitHub Pages hosting is discontinued, so the static-export pipeline is now dead
weight. This change deletes `export.py` and the committed `docs/` output, drops the
unused `frozen-flask` dependency, and purges GitHub-Pages / `docs/` / `export.py`
references from the live docs (`README.md`, `CLAUDE.md`, `memory/project_context.md`)
and a stale code comment (`static/js/autocomplete.js`). The running Flask app is
untouched: `export.py` imports `app` (never the reverse), nothing imports
`frozen-flask` (the exporter uses Flask's `test_client`, not the `Freezer`), and the
`/commanders.json` route stays because the **live** autocomplete depends on it.

## User Story
As a maintainer, I want the discontinued GitHub Pages static export removed, so that
the app is a single local-Flask target with no dead export code to maintain.

## Metadata
| Field | Value |
|-------|-------|
| Type | REFACTOR (cleanup) |
| Complexity | LOW |
| GitHub Issue | #16 |
| Systems Affected | build/export tooling, `requirements.txt`, project docs, one JS comment |

---

## Spike Findings (verified 2026-06-20)

- **Tracked files to remove** (`git ls-files`): `export.py`, and `docs/` →
  `docs/index.html`, `docs/atraxa-praetors-voice.html`, `docs/commanders.json`,
  `docs/static/css/style.css`, `docs/static/js/autocomplete.js`,
  `docs/static/js/filters.js`. All are git-tracked → use `git rm` (not gitignored).
- **`frozen-flask` is already unused**: no `.py` file imports `frozen_flask` /
  `flask_frozen` / `Freezer` (grep of live code = none). `export.py` renders via
  `app.test_client().get(...)`, not the Freezer. Safe to drop from
  `requirements.txt:5`.
- **App does not depend on export**: `export.py:18` does `from app import app`
  (one-directional). `app.py` imports only `flask` + `services`. Removing the
  exporter cannot break `python app.py`.
- **Keep `/commanders.json`**: `app.py:25` serves it; `static/js/autocomplete.js:17`
  fetches `commanders.json` (relative → `/commanders.json` on the landing page). This
  is **live** autocomplete, not an export artifact. Do NOT remove the route. Only the
  *static* copy (`docs/commanders.json`) goes, with `docs/`.
- **Doc reference inventory** (live docs only — see "Out of Scope" for what to leave):
  - `README.md:26-40` — "Generate Static Export" + "GitHub Pages Setup" sections.
  - `CLAUDE.md` lines 15, 28, 44-45, 79, 133-135, 246 — export/Pages mentions.
  - `memory/project_context.md` line 9 (clause) and the decision block lines 20-22.
  - `static/js/autocomplete.js:16` — comment mentioning the static export.

---

## Patterns to Follow

This is a deletion/cleanup task — the "pattern" is consistency with how the live app
and docs already describe themselves.

### Live autocomplete fetch — keep working, just fix the comment
```javascript
// SOURCE: static/js/autocomplete.js:15-17
  // Fetch the commander-name list once (relative path resolves to the
  // /commanders.json route live, or docs/commanders.json in the static export).
  fetch('commanders.json')
```
The fetch itself stays; drop only the "or docs/commanders.json in the static export"
clause so the comment matches a local-only app.

### Requirements format
```
// SOURCE: requirements.txt:1-7
flask>=3.0
pyedhrec==0.0.2
requests>=2.31
ijson>=3.2
frozen-flask>=1.0   <-- remove this line
flake8>=7.0
black>=26.0
```

### Memory entry format (for the project_context.md edit)
```
// SOURCE: memory/project_context.md:14-16  (a decision block: Fact/Why/How, fenced by ---)
**Fact/Decision**: ...
**Why**: ...
**How to apply**: ...
```
Rewrite the GitHub Pages decision in this same shape rather than just deleting it, so
the reversal is recorded (memory should reflect the *current* decision).

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `export.py` | DELETE | Static site generator — discontinued. |
| `docs/` (6 tracked files) | DELETE | Committed GitHub Pages output — discontinued. |
| `requirements.txt` | UPDATE | Drop unused `frozen-flask`. |
| `static/js/autocomplete.js` | UPDATE | Comment-only: drop static-export mention. |
| `README.md` | UPDATE | Remove "Generate Static Export" + "GitHub Pages Setup" sections. |
| `CLAUDE.md` | UPDATE | Remove export/`/docs`/GitHub-Pages guidance. |
| `memory/project_context.md` | UPDATE | Record that GitHub Pages export is discontinued; fix the stale clause. |

No files are created.

---

## Tasks

Execute in order. Each task is atomic and verifiable.

### Task 1: Delete the export pipeline files (git-tracked)
- **Files**: `export.py`, `docs/`
- **Action**: DELETE
- **Implement**: Remove from the working tree and the index:
  ```bash
  git rm export.py
  git rm -r docs
  ```
  (Both are tracked; `git rm` stages the deletions. `docs/` contains 6 tracked files
  incl. `docs/static/`.)
- **Validate**: `test ! -e export.py && test ! -e docs && echo OK` ; `git status` shows
  the deletions staged.

### Task 2: Drop the unused frozen-flask dependency
- **File**: `requirements.txt`
- **Action**: UPDATE
- **Implement**: Delete the line `frozen-flask>=1.0` (line 5). Leave the other 6 lines
  intact (`flask`, `pyedhrec`, `requests`, `ijson`, `flake8`, `black`).
- **Mirror**: `requirements.txt:1-7`.
- **Validate**: `grep -i frozen requirements.txt` returns nothing.

### Task 3: Fix the stale static-export comment in autocomplete.js
- **File**: `static/js/autocomplete.js`
- **Action**: UPDATE (comment only — no behavior change)
- **Implement**: Change the comment at lines 15-16 so it no longer references the
  static export. Replace:
  ```
  // Fetch the commander-name list once (relative path resolves to the
  // /commanders.json route live, or docs/commanders.json in the static export).
  ```
  with:
  ```
  // Fetch the commander-name list once from the /commanders.json route
  // (relative path resolves against the landing page).
  ```
  Do NOT touch the `fetch('commanders.json')` call.
- **Mirror**: `static/js/autocomplete.js:15-17`.
- **Validate**: `grep -in "static export\|docs/commanders" static/js/autocomplete.js`
  returns nothing.

### Task 4: Remove export/GitHub-Pages sections from README.md
- **File**: `README.md`
- **Action**: UPDATE
- **Implement**: Delete the two sections spanning lines 26-40:
  - `## Generate Static Export (for GitHub Pages)` (and its code block + description).
  - `## GitHub Pages Setup` (and its numbered list).
  Keep `## Local Setup`, `## Run Locally`, and `## How It Works`. Ensure a clean blank
  line between `## Run Locally` (ends line 24) and `## How It Works` (line 42).
- **Validate**: `grep -in "github pages\|export.py\|/docs" README.md` returns nothing.

### Task 5: Purge export/GitHub-Pages guidance from CLAUDE.md
- **File**: `CLAUDE.md`
- **Action**: UPDATE
- **Implement**: Remove or rewrite each reference so the file describes a local-Flask
  app with no static export:
  1. **Line 15** (Project Overview → Deployment): replace
     `**Deployment:** Flask dev server for local use. Static HTML export (via `flask freeze` / custom script) for GitHub Pages hosting.`
     with `**Deployment:** Flask dev server for local use only.`
  2. **Line 28** (Tech Stack table): delete the row
     `| Frozen-Flask or custom export | latest | Static HTML export for GitHub Pages |`.
  3. **Lines 44-45** (Commands block): delete the
     `# Static export (GitHub Pages)` comment and the `python export.py ...` line.
  4. **Line 79** (architecture tree): delete the
     `├── export.py  # Static site generator for GitHub Pages → /docs` line.
  5. **Lines 133-135** (Feature Spec): delete the entire
     `### Static Export (`/docs`)` subsection (its 3 bullets).
  6. **Line 246** (Notes): delete the bullet
     `- GitHub Pages serves from `/docs` on `master` branch — `export.py` must write there.`
  Leave all other content (Scryfall bulk store notes, algorithm, layer rules) intact.
  Line numbers are pre-edit; apply top-to-bottom or match on text to stay robust.
- **Validate**: `grep -in "github pages\|export.py\|frozen-flask\|static export\|/docs"
  CLAUDE.md` returns nothing (the only acceptable remaining `docs` hit is
  `memory/references.md | External systems — APIs, docs` on line ~226, which is
  unrelated prose).

### Task 6: Update project memory to record the reversal
- **File**: `memory/project_context.md`
- **Action**: UPDATE
- **Implement**:
  1. **Line 9**: drop the GitHub Pages clause. Change
     `**Why**: Simplest stack that runs locally and can export static HTML for GitHub Pages. No need for scalability.`
     to `**Why**: Simplest stack that runs locally. No need for scalability.`
  2. **Lines 20-22** (the GitHub Pages decision block): replace the Fact/Why/How with a
     reversal entry, keeping the surrounding `---` fences:
     ```
     **Fact/Decision**: GitHub Pages static export was DISCONTINUED on 2026-06-20.
     `export.py`, the `docs/` output, and the `frozen-flask` dep were removed (issue #16).
     **Why**: The app is now local-Flask only; maintaining pre-generated static HTML for
     a hosted site was dropped scope.
     **How to apply**: Do not reintroduce a static/hosted export. The app runs solely via
     `python app.py`. The `/commanders.json` route stays — it powers the live autocomplete,
     not an export.
     ```
  No `MEMORY.md` index change is needed (the `project_context.md` pointer still holds).
- **Mirror**: `memory/project_context.md:14-16` (decision-block shape).
- **Validate**: `grep -n "discontinued\|2026-06-20" memory/project_context.md` shows the
  new entry; no remaining claim that the app *exports for GitHub Pages*.

### Task 7: Confirm the app still runs with the pipeline gone
- **File**: n/a (runtime verification)
- **Action**: verify
- **Implement**:
  1. `python -c "import app"` — imports cleanly (no reference to `export`/`frozen_flask`).
  2. `python app.py`, load `/` — landing page renders, autocomplete still fetches
     `/commanders.json` (Network tab 200). Optionally load
     `/commander/atraxa-praetors-voice` to confirm a full page still renders.
- **Validate**: app boots; `/commanders.json` returns the name list; no import errors.

---

## Validation Sequence

```bash
# From repo root, after all tasks
flake8 .
python -m py_compile app.py services/edhrec.py services/scryfall.py services/analysis.py services/bulk.py
python -c "import app"          # app imports without export.py / frozen-flask
# Reference sweep — all should return nothing in live code/docs:
grep -rin "export.py\|frozen-flask\|github pages" README.md CLAUDE.md requirements.txt static/ services/ app.py
# Manual: python app.py -> load / and confirm autocomplete works
```

(Note: `.agents/plans/`, `.agents/PRDs/`, and `AGENTIC-ENGINEERING-GUIDE.md` will still
contain historical "export"/"GitHub Pages" mentions by design — see Out of Scope.)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Removing `/commanders.json` would break live autocomplete | Out of scope by design — only `docs/commanders.json` (the static copy) is removed; the route at `app.py:25` stays. Task 7 verifies autocomplete still works. |
| `frozen-flask` thought to be in use | Verified no `.py` imports it (exporter uses `test_client`); removal is dependency-list only. |
| Deleting `docs/` loses committed history | History is preserved in git; `git rm` only removes from HEAD going forward, consistent with discontinuing the feature. |
| Editing CLAUDE.md by stale line numbers after earlier edits shift them | Apply edits top-to-bottom or match on the quoted text rather than raw line numbers. |

---

## Out of Scope (leave unchanged)

- **`.agents/plans/*` and `.agents/PRDs/*`** — historical artifacts (e.g.
  `issue-5-static-export.plan.md`); they record what was done at the time.
- **`AGENTIC-ENGINEERING-GUIDE.md`, `CODEBASE-GUIDE.md`** — generic/process guides;
  `CODEBASE-GUIDE.md`'s `export` hits are TypeScript sample code, not this app.
- **`/commanders.json` route** (`app.py:25`) and the live `autocomplete.js` fetch.
- Any replacement or hosted deployment (explicitly not reintroducing static/cloud).

---

## Acceptance Criteria

- [ ] `export.py` and `docs/` deleted (git rm), tree no longer contains them.
- [ ] `frozen-flask` removed from `requirements.txt`.
- [ ] No export/freeze/GitHub-Pages references remain in live code or docs
      (`README.md`, `CLAUDE.md`, `static/js/autocomplete.js`, `memory/project_context.md`).
- [ ] `memory/project_context.md` records the discontinuation (2026-06-20).
- [ ] `python app.py` runs; landing page + `/commanders.json` autocomplete still work.
- [ ] `flake8 .` clean.
- [ ] Follows CLAUDE.md conventions (no behavioral change to the live app).
- [ ] GitHub Issue #16 criteria satisfied.
```
