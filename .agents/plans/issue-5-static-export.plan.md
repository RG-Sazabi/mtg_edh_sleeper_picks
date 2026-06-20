# Plan: Issue #5 — Static HTML Export for GitHub Pages

## Summary
Create `export.py` which renders commander pages to `docs/{slug}.html` using Flask's test client, copies `static/` assets to `docs/static/`, and writes a hand-crafted `docs/index.html` listing all exported commanders as clickable links. Because `base.html` uses `url_for()` which produces absolute paths (`/static/...`, `/`), the rendered HTML must be post-processed to replace these with relative paths before writing to disk. Create `README.md` with local run, export, and GitHub Pages setup instructions.

## User Story
As a deckbuilder, I want to run a single script that generates static HTML files I can push to GitHub Pages, so that I can share or revisit analysis results without running a local server.

## Metadata
| Field | Value |
|-------|-------|
| Type | NEW_CAPABILITY |
| Complexity | LOW |
| GitHub Issue | #5 |
| Systems Affected | export.py (new), README.md (new), docs/ (generated, not committed as source) |

---

## Key Technical Issues

### Asset path problem
`base.html` uses Jinja `url_for()` which Flask resolves to absolute paths:
- `url_for('static', filename='css/style.css')` → `/static/css/style.css`
- `url_for('index')` → `/`

These work with Flask's dev server but **break when HTML is opened directly from the filesystem**. The browser interprets `/static/` as the root of the current drive, not relative to the HTML file.

**Fix**: After rendering each page via `app.test_client()`, string-replace the rendered HTML:
```python
html = html.replace('href="/static/', 'href="static/')
html = html.replace('src="/static/',  'src="static/')
html = html.replace('href="/"',       'href="index.html"')
```
All commander pages and the index are in the same `docs/` directory, so `static/css/style.css` (relative, no leading slash) correctly resolves to `docs/static/css/style.css`.

### Static index page
The standard `index.html` template has a POST form — it won't work without a server. Instead, `export.py` writes a hand-crafted `docs/index.html` that lists each exported commander as a hyperlink. Simple, functional, no server required.

### `app.test_client()` and module-level state
`scryfall._otag_index` is a module-level dict. The test client reuses the same Python process, so the otag index and `_card_cache` stay warm across multiple commander exports in a single `export.py` run. This is intentional and good — first commander pays the 17MB download cost; subsequent ones are much faster.

### `docs/` directory in `.gitignore`
Generated HTML files in `docs/` should NOT be in `.gitignore` — GitHub Pages needs them committed. Verify `.gitignore` does not exclude `docs/`.

---

## Files to Change

| File | Action | Purpose |
|------|--------|---------|
| `export.py` | CREATE | Static site generator |
| `README.md` | CREATE | Local run + export + GitHub Pages setup instructions |

---

## Tasks

### Task 1: Check .gitignore for docs/ exclusion
- **Action**: READ `.gitignore`, verify `docs/` or `docs` is not listed.
- **If excluded**: Remove that line so GitHub Pages can see the generated files.
- **Validate**: `docs/` is not ignored.

---

### Task 2: Create export.py
- **File**: `export.py`
- **Action**: CREATE
- **Implement**:

```python
"""
Static site generator for GitHub Pages.

Usage:
    python export.py "Atraxa, Praetors' Voice" ["Korvold, Fae-Cursed King" ...]

Renders each commander page to docs/{slug}.html using Flask's test client,
copies static/ assets to docs/static/, and writes docs/index.html with links
to all exported commanders.
"""
import sys
import shutil
import logging
from pathlib import Path

from app import app
from services.edhrec import slugify

logging.basicConfig(level=logging.WARNING)

DOCS_DIR = Path("docs")


def _fix_paths(html: str) -> str:
    """Replace absolute Flask-generated paths with relative paths for filesystem serving."""
    html = html.replace('href="/static/', 'href="static/')
    html = html.replace('src="/static/', 'src="static/')
    html = html.replace('href="/"', 'href="index.html"')
    return html


def export_commander(name: str) -> str | None:
    """Render a commander page to docs/{slug}.html. Returns slug on success, None on failure."""
    slug = slugify(name)
    with app.test_client() as client:
        response = client.get(f"/commander/{slug}")
    if response.status_code == 200:
        html = _fix_paths(response.data.decode("utf-8"))
        out_path = DOCS_DIR / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"  Exported: {out_path}")
        return slug
    print(f"  FAILED ({response.status_code}): /commander/{slug}")
    return None


def export_index(exported: list[tuple[str, str]]) -> None:
    """Write docs/index.html listing all exported commanders as links."""
    items = "\n    ".join(
        f'<li><a href="{slug}.html">{name}</a></li>'
        for name, slug in exported
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MTG EDH Sleeper Picks</title>
  <link rel="stylesheet" href="static/css/style.css">
</head>
<body>
  <nav><a href="index.html">MTG EDH Sleeper Picks</a></nav>
  <main>
    <h1>MTG EDH Sleeper Picks</h1>
    <p>Pre-generated commander analyses. Run <code>python export.py "Commander Name"</code> locally to regenerate.</p>
    <ul>
    {items}
    </ul>
  </main>
</body>
</html>"""
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"  Exported: {out}")


def main() -> None:
    names = sys.argv[1:]
    if not names:
        print("Usage: python export.py \"Commander Name\" [\"Another Commander\" ...]")
        sys.exit(1)

    DOCS_DIR.mkdir(exist_ok=True)

    print("Copying static assets...")
    shutil.copytree("static", DOCS_DIR / "static", dirs_exist_ok=True)

    exported: list[tuple[str, str]] = []
    for name in names:
        print(f"Exporting: {name}")
        slug = export_commander(name)
        if slug:
            exported.append((name, slug))

    print("Writing index...")
    export_index(exported)

    print(f"\nDone. {len(exported)}/{len(names)} commanders exported to {DOCS_DIR}/")


if __name__ == "__main__":
    main()
```

- **Validate**: `"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -m py_compile export.py`

---

### Task 3: Lint export.py
- **Action**: VALIDATE
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" export.py --max-line-length=119
  ```
- Fix all errors.

---

### Task 4: Create README.md
- **File**: `README.md`
- **Action**: CREATE
- **Implement**:

```markdown
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

## Generate Static Export (for GitHub Pages)

```bash
python export.py "Atraxa, Praetors' Voice" "Korvold, Fae-Cursed King"
```

This creates `docs/atraxa-praetors-voice.html`, `docs/korvold-fae-cursed-king.html`, and `docs/index.html`. Commit and push the `docs/` folder.

## GitHub Pages Setup

1. Push this repo to GitHub.
2. Go to **Settings → Pages**.
3. Under **Source**, select **Deploy from a branch**.
4. Set branch to `master` and folder to `/docs`.
5. Save. Your site will be live at `https://<username>.github.io/<repo>/`.

## How It Works

1. Fetches EDHRec recommended cards for the commander via PyEDHRec.
2. Enriches each card with Scryfall oracle tags, price (TCGPlayer via Scryfall), and rarity.
3. Runs weighted term-frequency analysis: tags on high-synergy EDHRec cards get higher scores.
4. Scores every card in the commander's color identity by how many high-value tags it shares.
5. Displays the standard EDHRec list plus a **Slept On** section of top-scoring underplayed cards.
```

- **Validate**: File exists and is readable.

---

### Task 5: Smoke test the export
- **Action**: VALIDATE (requires network, takes ~2–5 min)
- **Command**:
  ```bash
  "C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" export.py "Atraxa, Praetors' Voice"
  ```
- **Expected output**:
  ```
  Copying static assets...
  Exporting: Atraxa, Praetors' Voice
    Exported: docs/atraxa-praetors-voice.html
  Writing index...
    Exported: docs/index.html

  Done. 1/1 commanders exported to docs/
  ```
- **Then verify**:
  - `docs/atraxa-praetors-voice.html` exists and is non-empty
  - `docs/static/css/style.css` exists
  - `docs/static/js/filters.js` exists
  - `docs/index.html` exists with a link to `atraxa-praetors-voice.html`

---

### Task 6: Open static HTML in browser and verify
- **Action**: VALIDATE (manual)
- Open `docs/atraxa-praetors-voice.html` directly in a browser (no server — use `file:///` or just double-click)
- **Check**:
  - [ ] Page renders with CSS styles applied (dark background, card grid)
  - [ ] Cards display with images, names, prices, rarities
  - [ ] Slept On section shows scored cards
  - [ ] Price cap input hides/shows cards without page reload
  - [ ] Pauper toggle works without page reload
  - [ ] N slider works without page reload
  - [ ] Nav "MTG EDH Sleeper Picks" link goes to `index.html` (not `/`)
  - [ ] DevTools console: zero errors

---

## Validation Sequence

```bash
# 1. Compile
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" -m py_compile export.py

# 2. Lint
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/flake8" export.py --max-line-length=119

# 3. Run export (Task 5)
"C:/Users/zanri/Documents/python projects/mtg_edh_sleeper_picks/.venv/Scripts/python" export.py "Atraxa, Praetors' Voice"

# 4. Open docs/atraxa-praetors-voice.html in browser (Task 6)
```

---

## Acceptance Criteria

- [ ] `export.py` exists and accepts one or more commander names as CLI args
- [ ] `_fix_paths()` replaces `/static/` → `static/` and `href="/"` → `href="index.html"` in rendered HTML
- [ ] `docs/{slug}.html` is written for each successfully exported commander
- [ ] `docs/static/` contains `css/style.css` and `js/filters.js`
- [ ] `docs/index.html` lists all exported commanders as clickable links to their pages
- [ ] `flake8 export.py --max-line-length=119` passes with zero errors
- [ ] `docs/` is NOT in `.gitignore`
- [ ] Opening `docs/atraxa-praetors-voice.html` in a browser (no server) shows styled, populated page
- [ ] All four filters work in the static page (JS reads relative `static/js/filters.js`)
- [ ] Nav link goes to `index.html`, not `/`
- [ ] `README.md` exists with local run, export, and GitHub Pages setup instructions
- [ ] Resolves GitHub Issue #5
