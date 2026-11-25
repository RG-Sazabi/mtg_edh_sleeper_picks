"""Archidekt deck import (offline, recorded deck 1727139)."""

import pytest

from services import archidekt
from tests.helpers import load_json


def test_first_category_rule_keeps_100_cards():
    deck = load_json("archidekt_1727139.json")
    assert len(deck["cards"]) == 200  # incl. removed / maybeboard entries
    names = archidekt._card_names(deck)
    assert len(names) == 100
    assert len(set(names)) == 100


def test_cards_whose_first_category_is_excluded_are_dropped():
    deck = load_json("archidekt_1727139.json")
    excluded = {c["name"] for c in deck["categories"] if not c["includedInDeck"]}
    kept = set(archidekt._card_names(deck))
    # e.g. ["Removed From Deck", "Ramp"]: out, even though Ramp is included.
    mixed = [
        c
        for c in deck["cards"]
        if c["categories"]
        and c["categories"][0] in excluded
        and any(cat not in excluded for cat in c["categories"][1:])
    ]
    assert mixed, "fixture should contain a removed card with an included 2nd category"
    for c in mixed:
        assert archidekt._oracle_name(c) not in kept


def test_commanders_from_premier_category():
    deck = load_json("archidekt_1727139.json")
    assert archidekt._commander_names(deck) == [
        "Thrasios, Triton Hero",
        "Tymna the Weaver",
    ]


def test_get_deck_via_http(fake_http):
    deck = archidekt.get_deck("1727139")
    assert deck["deck_id"] == "1727139"
    assert len(deck["card_names"]) == 100
    assert fake_http.calls == ["https://archidekt.com/api/decks/1727139/"]
    assert archidekt.get_deck("999") is None  # 404 -> None, never raises


def test_get_deck_network_failure_is_none(fake_http):
    fake_http.fail_hosts.add("archidekt.com")
    assert archidekt.get_deck("1727139") is None


@pytest.mark.parametrize(
    "url,deck_id",
    [
        ("https://archidekt.com/decks/1727139", "1727139"),
        ("https://www.archidekt.com/decks/1727139/some_name?x=1#y", "1727139"),
        ("https://archidekt.com/decks/18289857/sup_esika", "18289857"),
        ("http://archidekt.com/api/decks/42/", "42"),
        ("  https://archidekt.com/decks/7  ", "7"),
        ("https://archidekt.com.evil.com/decks/1", None),
        ("https://evil.com/archidekt.com/decks/1", None),
        ("https://archidekt.com/decks/abc", None),
        ("archidekt.com/decks/1", None),
        ("", None),
    ],
)
def test_parse_deck_id(url, deck_id):
    assert archidekt.parse_deck_id(url) == deck_id
