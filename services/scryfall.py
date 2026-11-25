"""
Scryfall access layer.

Card attributes, oracle tags, and the color-identity pool are served from the
local bulk store (``services/bulk.py``) — no per-request network calls. A thin
live ``/cards/named`` fallback covers the rare card name missing from the bulk
snapshot.
"""

import logging
import time

import requests

from . import bulk

SCRYFALL_BASE = "https://api.scryfall.com"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}

# Per-card live fallback responses, cached for the lifetime of the process.
_card_cache: dict = {}
# Negative cache for the live fallback: name -> monotonic expiry. A name that
# failed (404, 429, network) isn't retried until it expires, so reloading a page
# full of not-yet-in-bulk names doesn't re-hit Scryfall every time.
_miss_cache: dict[str, float] = {}
MISS_TTL_SECONDS = 30 * 60
# Cap on the total time one request may spend in live fallback lookups; names
# left once it's spent get empty details (not negative-cached — never tried).
FALLBACK_BUDGET_SECONDS = 10.0
# When Scryfall keeps answering 429, pause *all* live fallback lookups (across
# requests) for this long instead of retrying name after name.
RATE_LIMIT_COOLDOWN_SECONDS = 60.0
_cooldown_until = 0.0

logger = logging.getLogger(__name__)


def warm_up() -> None:
    """Build the local bulk indices (downloads on first run / when stale)."""
    bulk.ensure_loaded()


def _get(url: str, params: dict = None, deadline: float | None = None) -> dict | None:
    """GET with 429 backoff. Never sleeps past ``deadline`` (time.monotonic()).
    Giving up on a 429 starts a global fallback cooldown."""
    global _cooldown_until
    for attempt in range(3):
        try:
            timeout = 15
            if deadline is not None:
                timeout = max(1.0, min(15.0, deadline - time.monotonic()))
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            time.sleep(0.15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = 2**attempt
                if deadline is not None and time.monotonic() + wait > deadline:
                    logger.warning("Scryfall 429 on %s; fallback budget spent", url)
                    _cooldown_until = time.monotonic() + RATE_LIMIT_COOLDOWN_SECONDS
                    return None
                logger.warning("Scryfall 429 on %s, retrying in %ss", url, wait)
                time.sleep(wait)
                continue
            logger.error("Scryfall GET %s returned %s", url, resp.status_code)
            return None
        except Exception as e:
            logger.error("Scryfall GET %s failed: %s", url, e)
            return None
    logger.error("Scryfall GET %s failed after 3 attempts (429)", url)
    _cooldown_until = time.monotonic() + RATE_LIMIT_COOLDOWN_SECONDS
    return None


def _empty_card_details() -> dict:
    return {
        "oracle_id": "",
        "otags": [],
        "type_line": "",
        "price_usd": None,
        "rarity": "",
        "ever_common": False,
        "image_uri": "",
    }


def _details_from_record(rec: dict) -> dict:
    """Shape a bulk record into the per-card details dict used by callers."""
    return {
        "oracle_id": rec["oracle_id"],
        "otags": bulk.otags_for(rec["oracle_id"]),
        "type_line": rec["type_line"],
        "price_usd": rec["price_usd"],
        "rarity": rec["rarity"],
        # Any paper printing is common (rarity stays the displayed printing's).
        "ever_common": rec["ever_common"],
        "image_uri": rec["image_uri"],
    }


def get_card_details(name: str, deadline: float | None = None) -> dict:
    """
    Look up a single card's details, preferring the local bulk store and falling
    back to a live ``/cards/named`` request for names absent from the snapshot.
    Failed lookups are negative-cached for ``MISS_TTL_SECONDS``; ``deadline``
    (time.monotonic()) bounds the live call — past it, no request is made.
    """
    rec = bulk.card_record(name)
    if rec is not None:
        return _details_from_record(rec)
    if name in _card_cache:
        return _card_cache[name]
    expiry = _miss_cache.get(name)
    if expiry is not None and expiry > time.monotonic():
        return _empty_card_details()
    now = time.monotonic()
    if now < _cooldown_until or (deadline is not None and now >= deadline):
        return _empty_card_details()  # not negative-cached: never tried
    data = _get(f"{SCRYFALL_BASE}/cards/named", {"exact": name}, deadline)
    if not data or data.get("object") == "error":
        _miss_cache[name] = time.monotonic() + MISS_TTL_SECONDS
        return _empty_card_details()
    oracle_id = data.get("oracle_id", "")
    price_usd_raw = data.get("prices", {}).get("usd")
    image_uri = data.get("image_uris", {}).get("normal", "")
    if not image_uri:
        faces = data.get("card_faces") or [{}]
        image_uri = faces[0].get("image_uris", {}).get("normal", "")
    result = {
        "oracle_id": oracle_id,
        "otags": bulk.otags_for(oracle_id),
        "type_line": data.get("type_line", ""),
        "price_usd": float(price_usd_raw) if price_usd_raw else None,
        "rarity": data.get("rarity", ""),
        "ever_common": data.get("rarity") == "common",
        "image_uri": image_uri,
    }
    _card_cache[name] = result
    return result


def get_cards_collection(names: list[str]) -> dict[str, dict]:
    """
    Details for many cards, keyed by name. Served from the local bulk store;
    any name missing from the snapshot falls back to a single live lookup, with
    all such lookups for this call sharing a ``FALLBACK_BUDGET_SECONDS`` budget.
    """
    result: dict[str, dict] = {}
    deadline = None  # started lazily, on the first name that needs the network
    for name in names:
        rec = bulk.card_record(name)
        if rec is not None:
            result[name] = _details_from_record(rec)
        else:
            if deadline is None:
                deadline = time.monotonic() + FALLBACK_BUDGET_SECONDS
            result[name] = get_card_details(name, deadline)
    return result


def get_color_identity_pool(color_identity: list[str]) -> list[dict]:
    """
    All commander-legal cards within the commander's color identity, in EDHRec
    rank order, shaped as scoring-ready card dicts. Pure local filter.
    """
    cards = []
    for rec in bulk.color_identity_pool(color_identity):
        cards.append(
            {
                "name": rec["name"],
                "oracle_id": rec["oracle_id"],
                "edhrec_category": "",
                "edhrec_synergy": 0.0,
                "edhrec_inclusion": 0.0,
                "otags": bulk.otags_for(rec["oracle_id"]),
                "type_line": rec["type_line"],
                "price_usd": rec["price_usd"],
                "rarity": rec["rarity"],
                "ever_common": rec["ever_common"],
                "image_uri": rec["image_uri"],
                "buzzword_score": 0.0,
            }
        )
    return cards
