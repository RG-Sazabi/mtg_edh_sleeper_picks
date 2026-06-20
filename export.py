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
    """Rewrite absolute Flask paths to relative ones for filesystem serving."""
    html = html.replace('href="/static/', 'href="static/')
    html = html.replace('src="/static/', 'src="static/')
    html = html.replace('href="/"', 'href="index.html"')
    return html


def export_commander(name: str) -> str | None:
    """Render a commander page to docs/{slug}.html. Returns slug or None."""
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
        f'<li><a href="{slug}.html">{name}</a></li>' for name, slug in exported
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
    <p>Pre-generated commander analyses. Run
    <code>python export.py "Commander Name"</code> locally to regenerate.</p>
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
        print('Usage: python export.py "Commander Name" ["Another Commander" ...]')
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
