"""
Re-record the offline test fixtures under ``tests/fixtures/``. Not run by pytest.

    python tests/build_fixtures.py fetch   # EDHRec / Archidekt / bulk listing
    python tests/build_fixtures.py bulk    # sample from cache/*.jsonl.gz

(run with the project venv's python).

``fetch`` makes five polite, spaced requests with the app's User-Agent. ``bulk``
reads the real bulk files the app downloaded into ``cache/`` (start the app once
first) and writes a small gzip JSON-Lines sample in the same format: every card
named in the EDHRec / Archidekt fixtures, the commanders, a set of edge cases
(meld, stickers, basics, DFC and "Partner with" commanders, a card whose cleanest
printing has no price), plus the most-played cards of each colour. Each card keeps
its cleanest printing and, when different, its cheapest paper printing; fields
the app never reads are stripped to keep the files small.

After re-recording, regenerate the golden Top 10 deliberately (see
``tests/test_scoring.py``) and review the diff.
"""

import gzip
import json
import os
import random
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services import bulk  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
CACHE = os.path.join(ROOT, "cache")
HEADERS = bulk.HEADERS

EDHREC = "https://json.edhrec.com/pages/commanders/{}.json"
REMOTE = {
    "edhrec_atraxa-praetors-voice.json": EDHREC.format("atraxa-praetors-voice"),
    "edhrec_the-ur-dragon.json": EDHREC.format("the-ur-dragon"),
    "edhrec_thrasios-triton-hero-tymna-the-weaver.json": EDHREC.format(
        "thrasios-triton-hero-tymna-the-weaver"
    ),
    "archidekt_1727139.json": "https://archidekt.com/api/decks/1727139/",
    "scryfall_bulk_data.json": "https://api.scryfall.com/bulk-data",
}

EDGE_CASES = [
    # meld results and their parts
    "Urza, Planeswalker",
    "Urza, Lord Protector",
    "The Mightstone and Weakstone",
    "Brisela, Voice of Nightmares",
    "Gisela, the Broken Blade",
    "Bruna, the Fading Light",
    # basics
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
    "Snow-Covered Forest",
    # commanders: DFC, Partner with pair, vehicle/Grist-style, odd slugs
    "Esika, God of the Tree // The Prismatic Bridge",
    "Pir, Imaginative Rascal",
    "Toothy, Imaginary Friend",
    "Grist, the Hunger Tide",
    "Hearthhull, the Worldseed",
    "Atraxa, Praetors' Voice",
    "The Ur-Dragon",
    "Tymna the Weaver",
    "Thrasios, Triton Hero",
    "Krenko, Mob Boss",
    "Lim-Dûl the Necromancer",
    # the morning's false N/A prices
    "Mana Confluence",
    "Boros Charm",
    "Siege-Gang Commander",
    "Blasphemous Act",
]

KEEP = {
    "object",
    "id",
    "oracle_id",
    "name",
    "lang",
    "released_at",
    "layout",
    "highres_image",
    "mana_cost",
    "cmc",
    "type_line",
    "oracle_text",
    "power",
    "toughness",
    "colors",
    "color_identity",
    "keywords",
    "all_parts",
    "legalities",
    "games",
    "oversized",
    "promo",
    "set",
    "set_type",
    "collector_number",
    "digital",
    "rarity",
    "border_color",
    "frame",
    "frame_effects",
    "full_art",
    "textless",
    "edhrec_rank",
    "prices",
    "card_faces",
    "image_uris",
}
FACE_KEEP = {
    "object",
    "name",
    "mana_cost",
    "type_line",
    "oracle_text",
    "power",
    "toughness",
    "colors",
    "image_uris",
}


def fetch() -> None:
    os.makedirs(FIX, exist_ok=True)
    for fname, url in REMOTE.items():
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        with open(os.path.join(FIX, fname), "w", encoding="utf-8") as fh:
            json.dump(resp.json(), fh, ensure_ascii=False, separators=(",", ":"))
        print(f"{fname}: {resp.status_code} {len(resp.content):,} bytes")
        time.sleep(1.5)


def _slim(card: dict) -> dict:
    out = {k: v for k, v in card.items() if k in KEEP}
    if "image_uris" in out:
        out["image_uris"] = {"normal": out["image_uris"].get("normal", "")}
    if "legalities" in out:
        out["legalities"] = {"commander": out["legalities"].get("commander")}
    if "prices" in out:
        out["prices"] = {"usd": out["prices"].get("usd")}
    if "all_parts" in out:
        out["all_parts"] = [
            {k: p.get(k) for k in ("object", "component", "name", "type_line")}
            for p in out["all_parts"]
        ]
    if "card_faces" in out:
        faces = []
        for face in out["card_faces"]:
            f = {k: v for k, v in face.items() if k in FACE_KEEP}
            if "image_uris" in f:
                f["image_uris"] = {"normal": f["image_uris"].get("normal", "")}
            faces.append(f)
        out["card_faces"] = faces
    return out


def _fixture_names() -> set[str]:
    names: set[str] = set(EDGE_CASES)
    for fname in REMOTE:
        if not fname.startswith("edhrec_"):
            continue
        with open(os.path.join(FIX, fname), encoding="utf-8") as fh:
            page = json.load(fh)
        jd = page["container"]["json_dict"]
        names.update(jd["card"].get("names") or [jd["card"]["name"]])
        for cl in jd.get("cardlists", []):
            names.update(cv["name"] for cv in cl.get("cardviews", []))
    with open(os.path.join(FIX, "archidekt_1727139.json"), encoding="utf-8") as fh:
        deck = json.load(fh)
    for c in deck["cards"]:
        names.add(c["card"]["oracleCard"]["name"])
    return names


def build_bulk(extra_per_color: int = 260, extra_random: int = 1800) -> None:
    wanted = _fixture_names()
    printings: dict[str, list[dict]] = {}
    for raw in bulk._iter_jsonl(os.path.join(CACHE, "default-cards.jsonl.gz")):
        if raw.get("lang") != "en" or not raw.get("oracle_id"):
            continue
        if raw.get("layout") in bulk._EXCLUDED_LAYOUTS:
            continue  # the app never indexes these (art series share names)
        printings.setdefault(raw["oracle_id"], []).append(_slim(raw))

    by_name: dict[str, str] = {}
    for oid, prints in printings.items():
        name = prints[0]["name"]
        by_name.setdefault(name, oid)
        by_name.setdefault(name.split(" // ")[0], oid)

    chosen = {by_name[n] for n in wanted if n in by_name}
    missing = sorted(n for n in wanted if n not in by_name)

    def _best(prints):
        return min(
            prints,
            key=lambda r: (
                bulk._printing_penalty(r),
                0 if r.get("highres_image") else 1,
                bulk._neg(r.get("released_at", "")),
            ),
        )

    legal = [
        oid
        for oid, prints in printings.items()
        if (prints[0].get("legalities") or {}).get("commander") == "legal"
        and prints[0].get("layout") not in bulk._EXCLUDED_LAYOUTS
    ]
    # most-played cards of each colour (and colourless), then a random tail
    for colour in ("W", "U", "B", "R", "G", ""):
        group = [
            oid
            for oid in legal
            if (colour in printings[oid][0].get("color_identity", []))
            or (not colour and not printings[oid][0].get("color_identity"))
        ]
        group.sort(key=lambda o: printings[o][0].get("edhrec_rank") or 10**9)
        chosen.update(group[:extra_per_color])
    rng = random.Random(1727139)
    chosen.update(rng.sample(sorted(set(legal) - chosen), extra_random))

    # one sticker sheet, and a card whose cleanest printing is unpriced
    stickers = [o for o, p in printings.items() if p[0].get("type_line") == "Stickers"]
    chosen.update(sorted(stickers)[:2])
    unpriced_cheap = None
    for oid in sorted(chosen):
        prints = printings[oid]
        best = _best(prints)
        paper = [p for p in prints if bulk._is_playable_paper(p)]
        if not (best.get("prices") or {}).get("usd") and any(
            (p.get("prices") or {}).get("usd") for p in paper
        ):
            unpriced_cheap = best["name"]
            break

    lines = []
    for oid in sorted(chosen):
        prints = printings[oid]
        keep = [_best(prints)]
        priced = [
            p
            for p in prints
            if bulk._is_playable_paper(p) and (p.get("prices") or {}).get("usd")
        ]
        if priced:
            cheapest = min(priced, key=lambda p: float(p["prices"]["usd"]))
            if cheapest is not keep[0]:
                keep.append(cheapest)
        lines += [json.dumps(p, ensure_ascii=False) for p in keep]

    with gzip.open(
        os.path.join(FIX, "bulk", "default-cards.jsonl.gz"),
        "wt",
        encoding="utf-8",
        compresslevel=9,
    ) as fh:
        fh.write("\n".join(lines) + "\n")

    tag_lines = []
    for tag in bulk._iter_jsonl(os.path.join(CACHE, "oracle-tags.jsonl.gz")):
        tag["taggings"] = [
            {"oracle_id": t["oracle_id"]}
            for t in tag.get("taggings") or []
            if t.get("oracle_id") in chosen
        ]
        slim = {
            k: tag.get(k)
            for k in ("object", "id", "slug", "type", "parent_ids", "taggings")
        }
        tag_lines.append(json.dumps(slim, ensure_ascii=False))
    with gzip.open(
        os.path.join(FIX, "bulk", "oracle-tags.jsonl.gz"),
        "wt",
        encoding="utf-8",
        compresslevel=9,
    ) as fh:
        fh.write("\n".join(tag_lines) + "\n")

    meta = json.load(open(os.path.join(CACHE, "bulk-meta.json"), encoding="utf-8"))
    with open(os.path.join(FIX, "bulk", "bulk-meta.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {k: {"updated_at": v["updated_at"]} for k, v in meta.items()}, fh, indent=2
        )
    print(f"{len(chosen)} cards, {len(lines)} printings, {len(tag_lines)} tags")
    print(f"unpriced-display example: {unpriced_cheap}")
    print(f"fixture names not in bulk ({len(missing)}): {missing}")


if __name__ == "__main__":
    os.makedirs(os.path.join(FIX, "bulk"), exist_ok=True)
    if sys.argv[1:] == ["fetch"]:
        fetch()
    elif sys.argv[1:] == ["bulk"]:
        build_bulk()
    else:
        sys.exit(__doc__)
