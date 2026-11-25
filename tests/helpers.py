"""Fixture loaders and assertion helpers shared by the offline tests and the
live canary."""

import copy
import gzip
import json
import re
from pathlib import Path

from services import analysis, edhrec, scryfall

FIXTURES = Path(__file__).parent / "fixtures"
BULK_FIXTURES = FIXTURES / "bulk"

EDHREC_PAGES = {
    "atraxa-praetors-voice": "edhrec_atraxa-praetors-voice.json",
    "the-ur-dragon": "edhrec_the-ur-dragon.json",
    "thrasios-triton-hero-tymna-the-weaver": (
        "edhrec_thrasios-triton-hero-tymna-the-weaver.json"
    ),
}
PAIRING_REDIRECTS = {
    "tymna-the-weaver-thrasios-triton-hero": "thrasios-triton-hero-tymna-the-weaver"
}


def load_json(name: str):
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


def edhrec_page(slug: str) -> dict:
    """A fresh (deep-copied) raw EDHRec page payload for a fixture slug."""
    return copy.deepcopy(cached_json(EDHREC_PAGES[slug]))


def edhrec_data(slug: str) -> dict:
    """The parsed ``container.json_dict`` the app works on (as _fetch_json_dict)."""
    payload = edhrec_page(slug)
    data = payload["container"]["json_dict"]
    data["panels"] = payload.get("panels", {})
    return data


_JSON_CACHE: dict = {}


def cached_json(name: str):
    if name not in _JSON_CACHE:
        _JSON_CACHE[name] = load_json(name)
    return _JSON_CACHE[name]


def raw_fixture_cards() -> list[dict]:
    """Every printing in the sample default-cards file, as raw Scryfall dicts."""
    with gzip.open(
        BULK_FIXTURES / "default-cards.jsonl.gz", "rt", encoding="utf-8"
    ) as fh:
        return [json.loads(line) for line in fh if line.strip()]


# Every category the EDHRec tab may show: the type-list headers, plus "Other"
# for a card whose type line is unknown.
TYPE_HEADERS = set(edhrec._TYPE_HEADERS.values())
META_HEADERS = {
    "New Cards",
    "Top Cards",
    "High Lift Cards",
    "High Synergy Cards",
    "Game Changers",
}


def assert_edhrec_page_contract(data: dict, expected_commanders: list[str]) -> list:
    """
    The EDHRec parsing contract the app relies on. Returns the parsed cards.
    Fails if a field rename / list-tag change would silently degrade the page.
    """
    cards = edhrec.cards_from_data(data)
    assert len(cards) >= 100, f"only {len(cards)} cards parsed"
    assert edhrec.contract_problems(data, cards) == []

    with_incl = [c for c in cards if c["edhrec_inclusion"] > 0]
    assert len(with_incl) >= 0.9 * len(
        cards
    ), f"only {len(with_incl)}/{len(cards)} cards have inclusion > 0"
    assert all(0 <= c["edhrec_inclusion"] <= 1 for c in cards)
    assert any(c["edhrec_synergy"] != 0 for c in cards)

    # Category = a type-list header or "" (meta/unknown list, slotted later);
    # a list tag never becomes a category.
    for c in cards:
        assert c["edhrec_category"] in TYPE_HEADERS | {""}, c
    tags = {cl.get("tag") for cl in data.get("cardlists", [])}
    assert tags <= edhrec._KNOWN_TAGS, f"unknown list tags: {tags - edhrec._KNOWN_TAGS}"
    assert tags & edhrec._TYPE_TAGS, "no type lists on the page"

    # Meta-list cards (Top/New/High Lift) are part of the scoring list, with real
    # inclusion, and uncategorised until assign_type_categories runs.
    by_name = {c["name"]: c for c in cards}
    for cl in data["cardlists"]:
        if cl["tag"] not in edhrec._META_TAGS:
            continue
        for cv in cl["cardviews"]:
            card = by_name[cv["name"]]
            assert card["edhrec_inclusion"] > 0, cv["name"]

    info = edhrec.commander_info_from_data(data)
    assert info is not None
    assert info["color_identity"] and set(info["color_identity"]) <= set("WUBRG")
    assert info["image_uri"].startswith("https://")
    commanders = edhrec.commanders_from_data(data)
    assert [c["name"] for c in commanders] == expected_commanders
    assert all(c["image_uri"].startswith("https://") for c in commanders)

    index = edhrec.inclusion_index_from_data(data)
    assert {analysis.normalize_name(c["name"]) for c in cards} <= set(index)
    return cards


def score_page(data: dict):
    """
    The route's scoring path (steps 2-5 of ``commander()``) for an EDHRec page
    on the default level / types-off. Returns ``(cards, feature_stats, slept_on)``.
    """
    info = edhrec.commander_info_from_data(data)
    cards = edhrec.cards_from_data(data)
    details = scryfall.get_cards_collection([c["name"] for c in cards])
    for c in cards:
        c.update(details.get(c["name"], scryfall._empty_card_details()))
    stats = analysis.compute_feature_stats(cards)
    weights = {s["feature"]: s["weight"] for s in stats}
    pool = scryfall.get_color_identity_pool(info["color_identity"])
    exclude = {analysis.normalize_name(info["name"])}
    exclude |= {
        analysis.normalize_name(c["name"]) for c in edhrec.commanders_from_data(data)
    }
    return cards, stats, analysis.score_cards(pool, weights, exclude)


_GRID_RE = re.compile(
    r'<div class="card-grid slept-on-grid"([^>]*)>(.*?)</div>\s*(?=<h3>|</section>)',
    re.S,
)
_NAME_RE = re.compile(r'<div class="card-item"\s+data-name="([^"]*)"')


def slept_on_grids(html: str) -> list[tuple[str, list[str]]]:
    """``[(grid attributes, [card names])]`` for every Slept On grid on a page."""
    import html as html_lib

    return [
        (attrs, [html_lib.unescape(n) for n in _NAME_RE.findall(body)])
        for attrs, body in _GRID_RE.findall(html)
    ]
