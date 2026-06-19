import logging

import requests
from pyedhrec import EDHRec

EDHREC_JSON_BASE = "https://json.edhrec.com/pages/commanders"
HEADERS = {"User-Agent": "mtg-edh-sleeper-picks/1.0 (personal project)"}

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "").replace(",", "")


def get_commander_info(commander_name: str) -> dict | None:
    slug = slugify(commander_name)
    url = f"{EDHREC_JSON_BASE}/{slug}.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        card = resp.json()["container"]["json_dict"]["card"]
        image_uri = ""
        image_uris = card.get("image_uris", [])
        if image_uris:
            image_uri = image_uris[0].get("normal", "")
        return {
            "name": card["name"],
            "color_identity": card["color_identity"],
            "image_uri": image_uri,
        }
    except Exception as e:
        logger.error("get_commander_info failed for %r: %s", commander_name, e)
        return None


def get_commander_cards(commander_name: str) -> list[dict]:
    try:
        edhrec = EDHRec()
        raw = edhrec.get_commander_cards(commander_name)
        seen = {}
        for category, cards in raw.items():
            for card in cards:
                name = card.get("name", "")
                if not name or name in seen:
                    continue
                potential = card.get("potential_decks") or 0
                inclusion_count = card.get("inclusion") or 0
                edhrec_inclusion = (inclusion_count / potential) if potential else 0.0
                seen[name] = {
                    "name": name,
                    "edhrec_category": category,
                    "edhrec_synergy": float(card.get("synergy", 0.0)),
                    "edhrec_inclusion": edhrec_inclusion,
                    "otags": [],
                    "price_usd": None,
                    "rarity": "",
                    "image_uri": "",
                    "buzzword_score": 0.0,
                }
        return list(seen.values())
    except Exception as e:
        logger.error("get_commander_cards failed for %r: %s", commander_name, e)
        return []
