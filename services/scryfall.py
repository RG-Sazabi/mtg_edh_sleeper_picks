import logging
import time
from collections import defaultdict

import requests

SCRYFALL_BASE = "https://api.scryfall.com"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}

_card_cache: dict = {}
_otag_index: dict = {}
_otag_index_loaded = False

logger = logging.getLogger(__name__)


def _load_otag_index() -> None:
    global _otag_index_loaded, _otag_index
    if _otag_index_loaded:
        return
    try:
        resp = requests.get(f"{SCRYFALL_BASE}/bulk-data", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        bulk_list = resp.json().get("data", [])
        download_uri = next(
            (item["download_uri"] for item in bulk_list if item["type"] == "oracle_tags"),
            None,
        )
        if not download_uri:
            logger.error("oracle_tags bulk entry not found in Scryfall bulk-data")
            return
        tag_resp = requests.get(download_uri, headers=HEADERS, timeout=120)
        tag_resp.raise_for_status()
        index = defaultdict(list)
        for tag_obj in tag_resp.json():
            slug = tag_obj.get("slug", "")
            for tagging in tag_obj.get("taggings", []):
                oid = tagging.get("oracle_id", "")
                if oid:
                    index[oid].append(slug)
        _otag_index = dict(index)
        _otag_index_loaded = True
    except Exception as e:
        logger.error("_load_otag_index failed: %s", e)


def _get(url: str, params: dict = None) -> dict | None:
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        time.sleep(0.1)
        if resp.status_code == 200:
            return resp.json()
        logger.error("Scryfall GET %s returned %s", url, resp.status_code)
        return None
    except Exception as e:
        logger.error("Scryfall GET %s failed: %s", url, e)
        return None


def _empty_card_details() -> dict:
    return {"otags": [], "price_usd": None, "rarity": "", "image_uri": ""}


def get_card_details(name: str) -> dict:
    if name in _card_cache:
        return _card_cache[name]
    data = _get(f"{SCRYFALL_BASE}/cards/named", {"exact": name})
    if not data or "object" not in data or data.get("object") == "error":
        return _empty_card_details()
    oracle_id = data.get("oracle_id", "")
    price_usd_raw = data.get("prices", {}).get("usd")
    price_usd = float(price_usd_raw) if price_usd_raw else None
    rarity = data.get("rarity", "")
    image_uri = data.get("image_uris", {}).get("normal", "")
    if not image_uri:
        faces = data.get("card_faces") or [{}]
        image_uri = faces[0].get("image_uris", {}).get("normal", "")
    _load_otag_index()
    otags = _otag_index.get(oracle_id, [])
    result = {
        "oracle_id": oracle_id,
        "otags": otags,
        "price_usd": price_usd,
        "rarity": rarity,
        "image_uri": image_uri,
    }
    _card_cache[name] = result
    return result


def get_color_identity_pool(color_identity: list[str]) -> list[dict]:
    _load_otag_index()
    color_string = "".join(sorted(color_identity))
    query = f"id<={color_string} f:edh"
    url = f"{SCRYFALL_BASE}/cards/search"
    params: dict | None = {"q": query, "order": "edhrec"}
    cards = []
    try:
        while url:
            data = _get(url, params)
            params = None
            if not data or data.get("object") == "error":
                break
            for card in data.get("data", []):
                oracle_id = card.get("oracle_id", "")
                price_usd_raw = card.get("prices", {}).get("usd")
                price_usd = float(price_usd_raw) if price_usd_raw else None
                image_uri = card.get("image_uris", {}).get("normal", "")
                if not image_uri:
                    faces = card.get("card_faces") or [{}]
                    image_uri = faces[0].get("image_uris", {}).get("normal", "")
                cards.append({
                    "name": card["name"],
                    "oracle_id": oracle_id,
                    "edhrec_category": "",
                    "edhrec_synergy": 0.0,
                    "edhrec_inclusion": 0.0,
                    "otags": _otag_index.get(oracle_id, []),
                    "price_usd": price_usd,
                    "rarity": card.get("rarity", ""),
                    "image_uri": image_uri,
                    "buzzword_score": 0.0,
                })
            if data.get("has_more"):
                url = data.get("next_page", "")
            else:
                url = ""
    except Exception as e:
        logger.error("get_color_identity_pool failed: %s", e)
    return cards
