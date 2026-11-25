import logging
import re
import unicodedata

import requests

from .analysis import normalize_name

EDHREC_JSON_BASE = "https://json.edhrec.com/pages/commanders"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}

logger = logging.getLogger(__name__)

# Type cardlists: each list's `header` becomes the card's EDHRec-tab category.
_TYPE_TAGS = {
    "creatures",
    "instants",
    "sorceries",
    "utilityartifacts",
    "enchantments",
    "battles",
    "planeswalkers",
    "utilitylands",
    "manaartifacts",
    "lands",
}

# Meta cardlists (New / Top / High Lift / High Synergy / Game Changers). EDHRec
# used to repeat these cards inside the type lists; as of Nov 2026 the lists are
# DISJOINT (0/10 topcards also appear in a type list), so skipping them would drop
# the commander's most-played cards from scoring and from the type groups. They
# are therefore part of the recommendation/scoring list, with no category of their
# own: assign_type_categories() slots them into their type group after enrichment.
# `highliftcards` replaced `highsynergycards` (Nov 2026); both are kept.
_META_TAGS = {
    "newcards",
    "topcards",
    "highliftcards",
    "highsynergycards",
    "gamechangers",
}

# Display-only "featured" rows shown at the top of the EDHRec tab, rendered in the
# page's own order. Subset of _META_TAGS (gamechangers intentionally omitted per
# AC #17). Any tag outside _TYPE_TAGS | _META_TAGS is "unknown": its cards are
# treated like meta cards (scored, slotted by type) and never become a category,
# and contract_problems() flags the tag so the drift is visible.
_FEATURED_TAGS = ("newcards", "topcards", "highliftcards", "highsynergycards")
_KNOWN_TAGS = _TYPE_TAGS | _META_TAGS

# Fallback headers for assign_type_categories() (EDHRec's own header text).
_TYPE_HEADERS = {
    "creatures": "Creatures",
    "planeswalkers": "Planeswalkers",
    "battles": "Battles",
    "lands": "Lands",
    "utilitylands": "Utility Lands",
    "instants": "Instants",
    "sorceries": "Sorceries",
    "manaartifacts": "Mana Artifacts",
    "utilityartifacts": "Utility Artifacts",
    "enchantments": "Enchantments",
}
# Card-type precedence for multi-type cards (creatures only ever land in
# Creatures, matching EDHRec): first type word found in the front face wins.
_TYPE_PRECEDENCE = (
    ("Creature", "creatures"),
    ("Planeswalker", "planeswalkers"),
    ("Battle", "battles"),
    ("Land", "lands"),
    ("Instant", "instants"),
    ("Sorcery", "sorceries"),
    ("Artifact", "utilityartifacts"),
    ("Enchantment", "enchantments"),
)

# Static fallback option sets for the budget/bracket selectors (issue #19).
# EDHRec's numbered game brackets are NOT exposed via the static JSON (403 on
# /bracket-N.json), so the bracket selector offers only the power scope that is
# exposed — cEDH. "" = Any in both cases.
BUDGET_OPTIONS = ("", "budget", "expensive")
BRACKET_OPTIONS = ("", "cedh")


def slugify(name: str) -> str:
    """
    EDHRec page slug for a card name (idempotent on an existing slug). Matches
    EDHRec's rule, verified live Nov 2026: accents folded (NFKD, combining marks
    dropped: "Éowyn" -> "eowyn"), ``/`` treated as a separator ("SP//dr" ->
    "sp-dr"), every other non-alphanumeric character dropped ("Mr. House" ->
    "mr-house", "H.E.R.B.I.E." -> "herbie", "Minsc & Boo" -> "minsc-boo"),
    whitespace/dash runs collapsed to one ``-``. The result is always
    ``[a-z0-9-]``, so it is safe to interpolate into a URL path.

    A double-faced card's full name ("Esika, God of the Tree // The Prismatic
    Bridge", as Archidekt reports it) slugs to its FRONT face, which is how
    EDHRec names DFC commander pages. Only the spaced `` // `` face separator
    splits, so "SP//dr, Piloted by Peni" keeps its whole name.
    """
    text = unicodedata.normalize("NFKD", name.split(" // ")[0])
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def _scope_url(slug: str, theme: str = "", budget: str = "") -> str:
    """
    Build an EDHRec scope-page URL: ``<slug>[/<theme>][/budget|expensive].json``.
    ``theme`` is a single tag or bracket slug (EDHRec allows one theme slot).
    """
    path = slugify(slug)
    if theme and is_safe_scope_slug(theme):  # never interpolate an unsafe value
        path += f"/{theme}"
    if budget in ("budget", "expensive"):
        path += f"/{budget}"
    return f"{EDHREC_JSON_BASE}/{path}.json"


# A theme tag / bracket value that may go into an EDHRec URL path segment.
_SAFE_SCOPE_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def is_safe_scope_slug(value: str) -> bool:
    """Pure: ``True`` if ``value`` is a plausible EDHRec tag/bracket slug."""
    return bool(value) and _SAFE_SCOPE_RE.fullmatch(value) is not None


# Fetch-failure kinds reported by fetch_commander_scope().
FETCH_NOT_FOUND = "not_found"  # 4xx, or a 200 without a page container
FETCH_NETWORK = "network"  # connection error, timeout, 5xx / 429


def _fetch_json_dict(url: str) -> tuple[dict | None, str | None]:
    """
    Single HTTP GET to an EDHRec page URL. Returns ``(data, None)`` with the
    parsed ``container.json_dict`` dict (commander card + all cardlists), or
    ``(None, FETCH_NOT_FOUND | FETCH_NETWORK)`` on error. The page's ``panels``
    block (theme ``taglinks`` etc.) lives at the response root, a sibling of
    ``container``; it is folded into the returned dict under ``panels`` so scope
    extractors like ``available_tags_from_data`` can read it from the single
    ``get_commander_data`` payload.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
    except requests.RequestException as e:
        logger.error("_fetch_json_dict network error for %r: %s", url, e)
        return None, FETCH_NETWORK
    if resp.status_code >= 500 or resp.status_code == 429:
        logger.error("_fetch_json_dict got HTTP %s for %r", resp.status_code, url)
        return None, FETCH_NETWORK
    try:
        resp.raise_for_status()
        payload = resp.json()
        data = payload["container"]["json_dict"]
        data["panels"] = payload.get("panels", {})
        return data, None
    except Exception as e:
        # 4xx (EDHRec answers 403 for unknown slugs), or a 200 without a page
        # container (e.g. a {"redirect": ...} stub for a reversed pairing).
        logger.error("_fetch_json_dict failed for %r: %s", url, e)
        return None, FETCH_NOT_FOUND


def fetch_commander_scope(
    slug: str, tag: str = "", budget: str = "", bracket: str = ""
) -> tuple[dict | None, str | None]:
    """
    Fetch the EDHRec page ``container.json_dict`` for a commander scope. Returns
    ``(data, None)`` or ``(None, error_kind)`` where ``error_kind`` is
    ``FETCH_NETWORK`` if any attempt failed at the network level, else
    ``FETCH_NOT_FOUND``. ``slug`` is re-slugified so callers can pass either a
    slug or a display name idempotently.

    ``theme`` = tag or bracket (tag wins; EDHRec allows one theme slug). On a
    non-200/parse error the most-specific scope is retried dropping the
    least-important segment in order (bracket -> budget -> base), so an
    unsupported combo degrades gracefully instead of failing. The scope actually
    served is recorded on the data as ``served_scope`` ``{"theme", "budget"}``
    so callers can tell the user about a fallback (``scope_fallback_warning``).
    """
    theme = tag or bracket
    # Candidate (theme, budget) tuples, most- to least-specific.
    attempts = [(theme, budget)]
    if bracket and tag:  # both set -> tag took the slot; also try tag-only
        attempts.append((tag, budget))
    if budget:
        attempts.append((theme, ""))
    attempts.append(("", ""))  # base, last resort
    error = FETCH_NOT_FOUND
    for th, bg in dict.fromkeys(attempts):  # dedupe, preserve order
        data, err = _fetch_json_dict(_scope_url(slug, th, bg))
        if data:
            data["served_scope"] = {"theme": th, "budget": bg}
            return data, None
        if err == FETCH_NETWORK:
            error = FETCH_NETWORK
    return None, error


def get_commander_data(
    slug: str, tag: str = "", budget: str = "", bracket: str = ""
) -> dict | None:
    """``fetch_commander_scope`` without the error kind: data or ``None``."""
    return fetch_commander_scope(slug, tag=tag, budget=budget, bracket=bracket)[0]


def served_scope(data: dict | None) -> tuple[str, str]:
    """Pure: the ``(theme, budget)`` a ``fetch_commander_scope`` payload served."""
    scope = (data or {}).get("served_scope") or {}
    return scope.get("theme", ""), scope.get("budget", "")


def scope_fallback_warning(
    data: dict | None, tag: str = "", budget: str = "", bracket: str = ""
) -> str:
    """
    Pure: a user-facing sentence when the served scope differs from the one the
    selectors ask for (that page failed to fetch, or a tag displaced the bracket
    from EDHRec's single theme slot), else ``""``. The UI keeps the user's
    selection, so without this the page would silently show a different scope.
    """
    if not data:
        return ""
    served_theme, served_budget = served_scope(data)
    notes: list[str] = []
    if tag and bracket:
        notes.append(
            f"Bracket '{bracket}' is not applied: EDHRec allows a theme or a "
            "bracket, not both, and the theme takes precedence."
        )
    wanted_theme = tag or bracket
    dropped = []
    if wanted_theme and served_theme != wanted_theme:
        dropped.append(f"{'theme' if tag else 'bracket'} '{wanted_theme}'")
    if budget and served_budget != budget:
        dropped.append(f"budget '{budget}'")
    if dropped:
        shown = []
        if served_theme:
            shown.append(f"'{served_theme}'")
        if served_budget:
            shown.append(f"'{served_budget}'")
        notes.append(
            f"Couldn't load EDHRec data for {' + '.join(dropped)}; showing "
            + (" + ".join(shown) if shown else "all cards for this commander")
            + " instead."
        )
    return " ".join(notes)


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
    if not isinstance(card, dict):
        return None
    name = card.get("name")
    color_identity = card.get("color_identity")
    if not name or not isinstance(color_identity, list):
        # A renamed key would otherwise be a KeyError -> 500 in the route.
        logger.error(
            "EDHRec commander card missing name/color_identity; keys: %s",
            sorted(card.keys()),
        )
        return None
    image_uri = ""
    image_uris = card.get("image_uris") or []
    if image_uris and isinstance(image_uris[0], dict):
        image_uri = image_uris[0].get("normal", "")
    return {
        "name": name,
        "color_identity": color_identity,
        "image_uri": image_uri,
    }


def contract_problems(data: dict, cards: list[dict]) -> list[str]:
    """
    Pure: cheap sanity checks on a parsed EDHRec page, so silent schema drift
    (e.g. issue #47's renamed deck-count field, which zeroed every inclusion and
    emptied Slept On) shows up as a visible warning instead of a quietly wrong
    page. ``cards`` is ``cards_from_data(data)``. Returns human-readable problems,
    empty when the page looks healthy.
    """
    problems: list[str] = []
    if not cards:
        problems.append("no cards could be parsed from the EDHRec page")
    else:
        with_inclusion = sum(1 for c in cards if c.get("edhrec_inclusion", 0) > 0)
        if with_inclusion * 2 < len(cards):
            problems.append(
                f"only {with_inclusion} of {len(cards)} EDHRec cards have an "
                "inclusion rate (EDHRec may have renamed a field)"
            )
    unknown = sorted(
        {
            str(cl.get("tag"))
            for cl in (data or {}).get("cardlists", [])
            if cl.get("tag") not in _KNOWN_TAGS
        }
    )
    if unknown:
        problems.append(f"unrecognised EDHRec card list(s): {', '.join(unknown)}")
    return problems


def commanders_from_data(data: dict) -> list[dict]:
    """
    Pure: one ``{"name", "image_uri"}`` per commander on the page. A single
    commander yields 1 entry; a partner pairing yields 2, read from the combined
    card's ``names`` / ``image_uris`` lists (each aligned by index). Falls back to
    the scalar ``name`` when ``names`` is absent.
    """
    if not data:
        return []
    card = data.get("card")
    if not card:
        return []
    names = card.get("names") or [card.get("name", "")]
    image_uris = card.get("image_uris", [])
    commanders = []
    for i, name in enumerate(names):
        image_uri = ""
        if i < len(image_uris) and isinstance(image_uris[i], dict):
            image_uri = image_uris[i].get("normal", "")
        commanders.append({"name": name, "image_uri": image_uri})
    return commanders


def resolve_pairing_slug(name_a: str, name_b: str) -> str:
    """
    Build the combined EDHRec slug for a two-commander pairing. EDHRec's pairing
    ordering isn't always alphabetical (notably backgrounds), and only one
    ordering returns a usable container, so try both and keep the first that
    yields valid data. Falls back to ``<a>-<b>`` if neither fetch succeeds.
    """
    sa, sb = slugify(name_a), slugify(name_b)
    for combo in (f"{sa}-{sb}", f"{sb}-{sa}"):
        if get_commander_data(combo):
            return combo
    return f"{sa}-{sb}"


def _inclusion_from_cardview(cv: dict) -> float:
    """
    Pure: fraction of potential decks that include the card. EDHRec renamed the
    deck-count field ``inclusion`` -> ``num_decks`` (July 2026); read the new name
    first and keep the old one as a fallback for any cached/older payloads.
    """
    potential = cv.get("potential_decks") or 0
    inclusion_count = cv.get("num_decks") or cv.get("inclusion") or 0
    return (inclusion_count / potential) if potential else 0.0


def _card_from_cardview(cv: dict, category: str) -> dict:
    """Pure: build a per-card scoring dict from an EDHRec cardview."""
    return {
        "name": cv.get("name", ""),
        "edhrec_category": category,
        "edhrec_synergy": float(cv.get("synergy") or 0.0),
        "edhrec_inclusion": _inclusion_from_cardview(cv),
        "otags": [],
        "type_line": "",
        "price_usd": None,
        "rarity": "",
        "image_uri": "",
        "buzzword_score": 0.0,
    }


def cards_from_data(data: dict) -> list[dict]:
    """
    Pure: the full recommendation/scoring list from every cardlist on the page,
    deduped by name (first occurrence wins). Type lists are read first so a card
    they contain keeps its list ``header`` as its category; cards that only appear
    in a meta or unknown list get ``edhrec_category = ""`` and are slotted into a
    type group by ``assign_type_categories`` once their type line is known. A list
    tag therefore never becomes a category by itself.
    """
    if not data:
        return []
    cardlists = data.get("cardlists", [])
    typed = [cl for cl in cardlists if cl.get("tag") in _TYPE_TAGS]
    untyped = [cl for cl in cardlists if cl.get("tag") not in _TYPE_TAGS]
    seen: dict[str, dict] = {}
    for cardlist in typed + untyped:
        category = (
            cardlist.get("header", "") if cardlist.get("tag") in _TYPE_TAGS else ""
        )
        for cv in cardlist.get("cardviews", []):
            name = cv.get("name", "")
            if not name or name in seen:
                continue
            seen[name] = _card_from_cardview(cv, category)
    return list(seen.values())


def _type_key(card: dict) -> str | None:
    """Pure: the EDHRec type-list tag a card belongs in, from its front face."""
    front = (card.get("type_line") or "").split("//")[0]
    otags = card.get("otags") or []
    for word, key in _TYPE_PRECEDENCE:
        if word not in front:
            continue
        if key == "utilityartifacts" and any("mana-rock" in t for t in otags):
            return "manaartifacts"
        if key == "lands" and "utility-land" in otags:
            return "utilitylands"
        return key
    return None


def assign_type_categories(cards: list[dict], data: dict | None = None) -> None:
    """
    Pure (mutates in place): give every card with an empty ``edhrec_category``
    (meta/unknown-list cards, see ``cards_from_data``) the header of its type
    group, derived from the enriched ``type_line`` / ``otags``. Uses the page's
    own header text for that type list when present. The mana-vs-utility artifact
    and land split is a heuristic (``mana-rock*`` / ``utility-land`` otags); a
    card with no type line falls into "Other".
    """
    headers = dict(_TYPE_HEADERS)
    for cl in (data or {}).get("cardlists", []):
        if cl.get("tag") in _TYPE_TAGS and cl.get("header"):
            headers[cl["tag"]] = cl["header"]
    for card in cards:
        if card.get("edhrec_category"):
            continue
        key = _type_key(card)
        card["edhrec_category"] = headers[key] if key else "Other"


def featured_sections_from_data(data: dict) -> list[dict]:
    """
    Ordered display-only rows (New / Top / High Lift / High Synergy) from the
    EDHRec page container, in the page's order. Each section:
    {"tag", "header", "cards": [<scoring dict>]}. Empty/missing lists are
    omitted so the template degrades gracefully. These dicts are display copies:
    the same cards also sit in ``cards_from_data`` (scored, grouped by type).
    """
    if not data:
        return []
    sections: list[dict] = []
    for cardlist in data.get("cardlists", []):
        tag = cardlist.get("tag")
        if tag not in _FEATURED_TAGS:
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
            inclusion = _inclusion_from_cardview(cv)
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
