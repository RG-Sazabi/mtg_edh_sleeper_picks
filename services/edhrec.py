import logging

import requests

from .analysis import normalize_name

EDHREC_JSON_BASE = "https://json.edhrec.com/pages/commanders"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}

logger = logging.getLogger(__name__)

# Meta cardlists duplicate cards already present in the type categories, so they
# are excluded from the recommendation/scoring list (their dedicated display is
# issue #17). They still feed the broader inclusion index.
_META_TAGS = {"newcards", "highsynergycards", "topcards", "gamechangers"}


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "").replace(",", "")


def get_commander_data(slug: str) -> dict | None:
    """
    Single HTTP GET to the stable EDHRec commander page. Returns the parsed
    ``container.json_dict`` dict (commander card + all 13 cardlists), or ``None``
    on any error. ``slug`` is re-slugified so callers can pass either a slug or a
    display name idempotently.
    """
    slug = slugify(slug)
    url = f"{EDHREC_JSON_BASE}/{slug}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()["container"]["json_dict"]
    except Exception as e:
        logger.error("get_commander_data failed for %r: %s", slug, e)
        return None


def commander_info_from_data(data: dict) -> dict | None:
    """
    Pure: extract commander display info (name, color_identity, image_uri) from a
    ``get_commander_data`` payload. Returns ``None`` if the card is absent.
    """
    if not data:
        return None
    card = data.get("card")
    if not card:
        return None
    image_uri = ""
    image_uris = card.get("image_uris", [])
    if image_uris:
        image_uri = image_uris[0].get("normal", "")
    return {
        "name": card["name"],
        "color_identity": card["color_identity"],
        "image_uri": image_uri,
    }


def _card_from_cardview(cv: dict, category: str) -> dict:
    """Pure: build a per-card scoring dict from an EDHRec cardview."""
    potential = cv.get("potential_decks") or 0
    inclusion_count = cv.get("inclusion") or 0
    edhrec_inclusion = (inclusion_count / potential) if potential else 0.0
    return {
        "name": cv.get("name", ""),
        "edhrec_category": category,
        "edhrec_synergy": float(cv.get("synergy") or 0.0),
        "edhrec_inclusion": edhrec_inclusion,
        "otags": [],
        "type_line": "",
        "price_usd": None,
        "rarity": "",
        "image_uri": "",
        "buzzword_score": 0.0,
    }


def cards_from_data(data: dict) -> list[dict]:
    """
    Pure: the type-category recommendation list (meta lists skipped), deduped by
    name (first occurrence wins), using each list's ``header`` as the category.
    """
    if not data:
        return []
    seen: dict[str, dict] = {}
    for cardlist in data.get("cardlists", []):
        if cardlist.get("tag") in _META_TAGS:
            continue
        category = cardlist.get("header", "")
        for cv in cardlist.get("cardviews", []):
            name = cv.get("name", "")
            if not name or name in seen:
                continue
            seen[name] = _card_from_cardview(cv, category)
    return list(seen.values())


def inclusion_index_from_data(data: dict) -> dict[str, dict]:
    """
    Pure: ``{ normalize_name(name): {"inclusion": float, "synergy": float} }``
    built from ALL cardlists (meta included) — the broadest inclusion source the
    page offers. On duplicate names, the first non-zero inclusion seen wins.
    """
    index: dict[str, dict] = {}
    if not data:
        return index
    for cardlist in data.get("cardlists", []):
        for cv in cardlist.get("cardviews", []):
            name = cv.get("name", "")
            if not name:
                continue
            key = normalize_name(name)
            potential = cv.get("potential_decks") or 0
            inclusion_count = cv.get("inclusion") or 0
            inclusion = (inclusion_count / potential) if potential else 0.0
            synergy = float(cv.get("synergy") or 0.0)
            existing = index.get(key)
            if existing is None:
                index[key] = {"inclusion": inclusion, "synergy": synergy}
            elif not existing["inclusion"] and inclusion:
                index[key] = {"inclusion": inclusion, "synergy": synergy}
    return index


def get_commander_info(commander_name: str) -> dict | None:
    data = get_commander_data(commander_name)
    return commander_info_from_data(data) if data else None


def get_commander_cards(slug: str) -> list[dict]:
    data = get_commander_data(slug)
    return cards_from_data(data) if data else []
