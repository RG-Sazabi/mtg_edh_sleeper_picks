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

# Display-only "featured" rows shown at the top of the EDHRec tab, in EDHRec's
# order. Subset of _META_TAGS (gamechangers intentionally omitted per AC #17).
_FEATURED_TAGS = ("newcards", "highsynergycards", "topcards")

# Static fallback option sets for the budget/bracket selectors (issue #19).
# EDHRec's numbered game brackets are NOT exposed via the static JSON (403 on
# /bracket-N.json), so the bracket selector offers only the power scope that is
# exposed — cEDH. "" = Any in both cases.
BUDGET_OPTIONS = ("", "budget", "expensive")
BRACKET_OPTIONS = ("", "cedh")


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "").replace(",", "")


def _scope_url(slug: str, theme: str = "", budget: str = "") -> str:
    """
    Build an EDHRec scope-page URL: ``<slug>[/<theme>][/budget|expensive].json``.
    ``theme`` is a single tag or bracket slug (EDHRec allows one theme slot).
    """
    path = slugify(slug)
    if theme:
        path += f"/{theme}"
    if budget in ("budget", "expensive"):
        path += f"/{budget}"
    return f"{EDHREC_JSON_BASE}/{path}.json"


def _fetch_json_dict(url: str) -> dict | None:
    """
    Single HTTP GET to an EDHRec page URL. Returns the parsed
    ``container.json_dict`` dict (commander card + all cardlists), or ``None`` on
    any error. The page's ``panels`` block (theme ``taglinks`` etc.) lives at the
    response root, a sibling of ``container``; it is folded into the returned dict
    under ``panels`` so scope extractors like ``available_tags_from_data`` can
    read it from the single ``get_commander_data`` payload.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        data = payload["container"]["json_dict"]
        data["panels"] = payload.get("panels", {})
        return data
    except Exception as e:
        logger.error("_fetch_json_dict failed for %r: %s", url, e)
        return None


def get_commander_data(
    slug: str, tag: str = "", budget: str = "", bracket: str = ""
) -> dict | None:
    """
    Fetch the EDHRec page ``container.json_dict`` for a commander scope. Returns
    the commander card + all cardlists, or ``None`` on error. ``slug`` is
    re-slugified so callers can pass either a slug or a display name idempotently.

    ``theme`` = tag or bracket (tag wins; EDHRec allows one theme slug). On a
    non-200/parse error the most-specific scope is retried dropping the
    least-important segment in order (bracket -> budget -> base), so an
    unsupported combo degrades gracefully instead of failing.
    """
    theme = tag or bracket
    # Candidate (theme, budget) tuples, most- to least-specific.
    attempts = [(theme, budget)]
    if bracket and tag:  # both set -> tag took the slot; also try tag-only
        attempts.append((tag, budget))
    if budget:
        attempts.append((theme, ""))
    attempts.append(("", ""))  # base, last resort
    for th, bg in dict.fromkeys(attempts):  # dedupe, preserve order
        data = _fetch_json_dict(_scope_url(slug, th, bg))
        if data:
            return data
    return None


def available_tags_from_data(data: dict) -> list[dict]:
    """
    Pure: the commander's theme tags from ``panels.taglinks``, as
    ``[{"slug", "value", "count"}]`` sorted by ``count`` desc. Returns ``[]`` if
    the panel is absent (graceful — the theme select then shows only "All cards").
    """
    if not data:
        return []
    taglinks = data.get("panels", {}).get("taglinks", [])
    tags = [
        {
            "slug": t.get("slug", ""),
            "value": t.get("value", ""),
            "count": t.get("count", 0),
        }
        for t in taglinks
        if t.get("slug")
    ]
    tags.sort(key=lambda t: t["count"], reverse=True)
    return tags


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


def featured_sections_from_data(data: dict) -> list[dict]:
    """
    Ordered display-only sections (New / High Synergy / Top) from the EDHRec
    page container. Each section: {"tag", "header", "cards": [<scoring dict>]}.
    Empty/missing lists are omitted so the template degrades gracefully. These
    cards are NOT part of the scoring dataset (see cards_from_data, which skips
    these tags) — they are rendered for parity only.
    """
    if not data:
        return []
    by_tag = {cl.get("tag"): cl for cl in data.get("cardlists", [])}
    sections: list[dict] = []
    for tag in _FEATURED_TAGS:
        cardlist = by_tag.get(tag)
        if not cardlist:
            continue
        header = cardlist.get("header", "")
        cards = [
            _card_from_cardview(cv, header)
            for cv in cardlist.get("cardviews", [])
            if cv.get("name")
        ]
        if cards:
            sections.append({"tag": tag, "header": header, "cards": cards})
    return sections


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
