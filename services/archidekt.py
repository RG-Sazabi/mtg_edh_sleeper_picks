"""
Archidekt deck-import boundary service.

All Archidekt HTTP calls and deck-URL parsing live here (layer rule, per
CLAUDE.md). Callers receive plain dicts / ``None`` — never exceptions, never
raw HTTP objects. The single numeric deck id extracted by ``parse_deck_id`` is
the only untrusted value that reaches the API path; the raw URL never does.

Deck JSON shape (verified against ``https://archidekt.com/api/decks/1/``):
- card name:            ``cards[].card.oracleCard.name``
- per-card categories:  ``cards[].categories`` (list of category-name strings)
- deck categories:      ``categories[]`` of ``{name, isPremier, includedInDeck}``
  — the command zone is the ``isPremier`` category; ``includedInDeck: false``
  marks maybeboard-style buckets.
"""

import logging
import re

import requests

HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}
API_BASE = "https://archidekt.com/api/decks"

logger = logging.getLogger(__name__)

# A deck URL we accept: an archidekt.com (optionally www.) host, an optional
# /api/ segment, /decks/, then the numeric id. Trailing slug/query/hash ignored.
_DECK_URL_RE = re.compile(
    r"^https?://(?:www\.)?archidekt\.com/(?:api/)?decks/(\d+)", re.IGNORECASE
)


def parse_deck_id(url: str) -> str | None:
    """
    Return the deck id if ``url`` is an archidekt.com deck URL, else ``None``.
    Host is validated and only ``\\d+`` after ``/decks/`` is extracted, so the
    raw URL is never interpolated into the API path.
    """
    if not url:
        return None
    match = _DECK_URL_RE.search(url.strip())
    return match.group(1) if match else None


def _fetch(deck_id: str) -> dict | None:
    """
    Single HTTP GET to the Archidekt deck API. Returns the parsed JSON dict, or
    ``None`` on any error. Mirrors ``edhrec._fetch_json_dict``.
    """
    url = f"{API_BASE}/{deck_id}/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("archidekt._fetch failed for %r: %s", url, e)
        return None


def _oracle_name(card: dict) -> str:
    """Pure: a card entry's oracle name, or ``""`` if any nested key is absent."""
    try:
        return card["card"]["oracleCard"]["name"]
    except (KeyError, TypeError):
        return ""


def _commander_names(deck: dict) -> list[str]:
    """
    Pure: the command-zone card names, de-duped, order-preserving. A card is a
    commander when its ``categories`` intersect the premier category set; the
    premier set is the deck categories flagged ``isPremier`` (fallback
    ``{"Commander"}`` when none are flagged).
    """
    premier = {
        c.get("name")
        for c in deck.get("categories", [])
        if c.get("isPremier")
    }
    if not premier:
        premier = {"Commander"}
    names: list[str] = []
    seen: set[str] = set()
    for card in deck.get("cards", []):
        if not set(card.get("categories") or []) & premier:
            continue
        name = _oracle_name(card)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _card_names(deck: dict) -> list[str]:
    """
    Pure: mainboard card names, de-duped, order-preserving. A card is included
    unless it has categories and none of them are deck categories included in
    the deck (drops maybeboard/considering). Cards with no categories default
    to included.
    """
    included = {
        c.get("name")
        for c in deck.get("categories", [])
        if c.get("includedInDeck", True)
    }
    names: list[str] = []
    seen: set[str] = set()
    for card in deck.get("cards", []):
        categories = card.get("categories") or []
        if categories and not (set(categories) & included):
            continue
        name = _oracle_name(card)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def get_deck(deck_id: str) -> dict | None:
    """
    Fetch + parse an Archidekt deck by id. Returns
    ``{"deck_id", "commander_names", "card_names"}`` or ``None`` on fetch
    failure. Never raises.
    """
    deck = _fetch(deck_id)
    if deck is None:
        return None
    return {
        "deck_id": deck_id,
        "commander_names": _commander_names(deck),
        "card_names": _card_names(deck),
    }
