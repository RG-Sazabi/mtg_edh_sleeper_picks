import logging

logger = logging.getLogger(__name__)


def compute_tf(edhrec_cards: list[dict]) -> dict[str, float]:
    """
    Build a term-frequency dict: otag -> sum of synergy weights across all EDHRec cards.
    Falls back to edhrec_inclusion as weight when edhrec_synergy is 0.0 (handles staples
    with no unique commander synergy that PyEDHRec returns with zero synergy).
    """
    tf: dict[str, float] = {}
    for card in edhrec_cards:
        weight = card.get("edhrec_synergy") or card.get("edhrec_inclusion", 0.0)
        for tag in card.get("otags", []):
            tf[tag] = tf.get(tag, 0.0) + weight
    return tf


def score_cards(
    color_pool: list[dict],
    tf: dict[str, float],
    edhrec_card_names: set[str],
) -> list[dict]:
    """
    Assign buzzword_score to each color-pool card not already in edhrec_card_names.
    Returns list sorted descending by buzzword_score, excluding zero-score cards.
    Does not mutate input dicts.
    """
    scored = []
    for card in color_pool:
        if card["name"] in edhrec_card_names:
            continue
        score = sum(tf.get(tag, 0.0) for tag in card.get("otags", []))
        if score > 0:
            card = dict(card)
            card["buzzword_score"] = score
            scored.append(card)
    scored.sort(key=lambda c: c["buzzword_score"], reverse=True)
    return scored


def apply_inclusion_cap(slept_on: list[dict], cap: float) -> list[dict]:
    """
    Filter out cards whose edhrec_inclusion exceeds cap.
    Note: color-pool cards have edhrec_inclusion=0.0 by default (they are not in
    the EDHRec list), so this filter primarily catches borderline cross-reference cases.
    """
    return [c for c in slept_on if c.get("edhrec_inclusion", 0.0) <= cap]
