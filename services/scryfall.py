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

logger = logging.getLogger(__name__)


def warm_up() -> None:
    """Build the local bulk indices (downloads on first run / when stale)."""
    bulk.ensure_loaded()


def _get(url: str, params: dict = None) -> dict | None:
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            time.sleep(0.15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = 2**attempt
                logger.warning("Scryfall 429 on %s, retrying in %ss", url, wait)
                time.sleep(wait)
                continue
            logger.error("Scryfall GET %s returned %s", url, resp.status_code)
            return None
        except Exception as e:
            logger.error("Scryfall GET %s failed: %s", url, e)
            return None
    logger.error("Scryfall GET %s failed after 3 attempts (429)", url)
    return None


def _empty_card_details() -> dict:
    return {
        "oracle_id": "",
        "otags": [],
        "type_line": "",
        "price_usd": None,
        "rarity": "",
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
        "image_uri": rec["image_uri"],
    }


def get_card_details(name: str) -> dict:
    """
    Look up a single card's details, preferring the local bulk store and falling
    back to a live ``/cards/named`` request for names absent from the snapshot.
    """
    rec = bulk.card_record(name)
    if rec is not None:
        return _details_from_record(rec)
    if name in _card_cache:
        return _card_cache[name]
    data = _get(f"{SCRYFALL_BASE}/cards/named", {"exact": name})
    if not data or data.get("object") == "error":
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
        "image_uri": image_uri,
    }
    _card_cache[name] = result
    return result


def get_cards_collection(names: list[str]) -> dict[str, dict]:
    """
    Details for many cards, keyed by name. Served from the local bulk store;
    any name missing from the snapshot falls back to a single live lookup.
    """
    result: dict[str, dict] = {}
    for name in names:
        rec = bulk.card_record(name)
        if rec is not None:
            result[name] = _details_from_record(rec)
        else:
            result[name] = get_card_details(name)
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
                "image_uri": rec["image_uri"],
                "buzzword_score": 0.0,
            }
        )
    return cards
