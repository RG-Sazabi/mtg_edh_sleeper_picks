"""EDHRec parsing contract, runtime contract check, and slugs (offline)."""

import pytest

from services import edhrec

from tests.helpers import (
    META_HEADERS,
    TYPE_HEADERS,
    assert_edhrec_page_contract,
    edhrec_data,
)

PAGES = [
    ("atraxa-praetors-voice", ["Atraxa, Praetors' Voice"]),
    ("the-ur-dragon", ["The Ur-Dragon"]),
    (
        "thrasios-triton-hero-tymna-the-weaver",
        ["Thrasios, Triton Hero", "Tymna the Weaver"],
    ),
]


# ---------------------------------------------------------------- (a) parsing


@pytest.mark.parametrize("slug,commanders", PAGES)
def test_page_contract(slug, commanders):
    assert_edhrec_page_contract(edhrec_data(slug), commanders)


@pytest.mark.parametrize("slug,commanders", PAGES)
def test_meta_cards_slotted_into_type_groups(slug, commanders, loaded_bulk):
    from services import scryfall

    data = edhrec_data(slug)
    cards = edhrec.cards_from_data(data)
    meta_names = {
        cv["name"]
        for cl in data["cardlists"]
        if cl["tag"] in edhrec._META_TAGS
        for cv in cl["cardviews"]
    }
    assert meta_names, "fixture has no meta lists"
    details = scryfall.get_cards_collection([c["name"] for c in cards])
    for c in cards:
        c.update(details[c["name"]])
    edhrec.assign_type_categories(cards, data)
    categories = {c["edhrec_category"] for c in cards}
    assert categories <= TYPE_HEADERS, categories - TYPE_HEADERS
    assert not categories & META_HEADERS
    slotted = {
        c["name"]: c["edhrec_category"] for c in cards if c["name"] in meta_names
    }
    assert set(slotted) == meta_names
    assert all(slotted.values())


def test_meta_lists_are_disjoint_and_counted_once():
    data = edhrec_data("the-ur-dragon")
    cards = edhrec.cards_from_data(data)
    names = [c["name"] for c in cards]
    assert len(names) == len(set(names))
    total = sum(len(cl["cardviews"]) for cl in data["cardlists"])
    assert len(cards) == total  # lists are disjoint today: nothing dropped


def test_featured_sections_in_page_order():
    sections = edhrec.featured_sections_from_data(edhrec_data("the-ur-dragon"))
    assert [s["tag"] for s in sections] == ["newcards", "topcards", "highliftcards"]
    assert [s["header"] for s in sections] == [
        "New Cards",
        "Top Cards",
        "High Lift Cards",
    ]
    assert all(s["cards"] for s in sections)
    # Atraxa's page has no High Lift list today.
    atraxa = edhrec.featured_sections_from_data(edhrec_data("atraxa-praetors-voice"))
    assert [s["tag"] for s in atraxa] == ["newcards", "topcards"]


def test_known_category_for_hellkite_courser(loaded_bulk):
    from services import scryfall

    data = edhrec_data("the-ur-dragon")
    cards = edhrec.cards_from_data(data)
    for c in cards:
        c.update(scryfall.get_card_details(c["name"]))
    edhrec.assign_type_categories(cards, data)
    top = [
        cv["name"]
        for cl in data["cardlists"]
        if cl["tag"] == "topcards"
        for cv in cl["cardviews"]
    ]
    by_name = {c["name"]: c for c in cards}
    for name in top:
        assert by_name[name]["edhrec_category"] in TYPE_HEADERS
    if "Hellkite Courser" in by_name:
        assert by_name["Hellkite Courser"]["edhrec_category"] == "Creatures"


def test_available_tags_sorted():
    tags = edhrec.available_tags_from_data(edhrec_data("atraxa-praetors-voice"))
    assert len(tags) > 20
    counts = [t["count"] for t in tags]
    assert counts == sorted(counts, reverse=True)
    assert all(edhrec.is_safe_scope_slug(t["slug"]) for t in tags)


def test_commander_info_guarded_against_missing_fields():
    data = edhrec_data("atraxa-praetors-voice")
    del data["card"]["name"]
    assert edhrec.commander_info_from_data(data) is None
    data = edhrec_data("atraxa-praetors-voice")
    data["card"]["color_identity"] = None
    assert edhrec.commander_info_from_data(data) is None
    assert edhrec.commander_info_from_data({}) is None


# ------------------------------------------------------- (b) contract check


def _rename_deck_count(data: dict) -> dict:
    for cl in data["cardlists"]:
        for cv in cl["cardviews"]:
            cv["deck_count"] = cv.pop("num_decks")
    return data


def test_contract_healthy_page_is_quiet():
    data = edhrec_data("atraxa-praetors-voice")
    assert edhrec.contract_problems(data, edhrec.cards_from_data(data)) == []


def test_contract_fires_on_renamed_deck_count():
    data = _rename_deck_count(edhrec_data("atraxa-praetors-voice"))
    cards = edhrec.cards_from_data(data)
    assert all(c["edhrec_inclusion"] == 0 for c in cards)
    problems = edhrec.contract_problems(data, cards)
    assert len(problems) == 1 and "inclusion rate" in problems[0]


def test_contract_fires_on_unknown_list_tag():
    data = edhrec_data("the-ur-dragon")
    data["cardlists"][2]["tag"] = "spicycards"  # was highliftcards
    data["cardlists"][2]["header"] = "Spicy Cards"
    cards = edhrec.cards_from_data(data)
    problems = edhrec.contract_problems(data, cards)
    assert problems == ["unrecognised EDHRec card list(s): spicycards"]
    # The unknown list never becomes a category; its cards are still scored.
    assert "Spicy Cards" not in {c["edhrec_category"] for c in cards}
    spicy = {cv["name"] for cv in data["cardlists"][2]["cardviews"]}
    assert spicy <= {c["name"] for c in cards}


@pytest.mark.parametrize("data", [{}, {"cardlists": []}, None])
def test_contract_fires_on_empty_page(data):
    problems = edhrec.contract_problems(data, edhrec.cards_from_data(data))
    assert problems == ["no cards could be parsed from the EDHRec page"]


def test_inclusion_reads_legacy_field_name():
    cv = {"name": "X", "inclusion": 50, "potential_decks": 200, "synergy": 0.1}
    assert edhrec._inclusion_from_cardview(cv) == 0.25
    cv = {"name": "X", "num_decks": 20, "potential_decks": 200}
    assert edhrec._inclusion_from_cardview(cv) == 0.1
    assert edhrec._inclusion_from_cardview({"num_decks": 5}) == 0.0


# --------------------------------------------------------------- (c) slugs

SLUG_CASES = [
    ("Atraxa, Praetors' Voice", "atraxa-praetors-voice"),
    ("Atraxa, Praetors’ Voice", "atraxa-praetors-voice"),  # curly quote
    ("The Ur-Dragon", "the-ur-dragon"),
    ("Kozilek, the Great Distortion", "kozilek-the-great-distortion"),
    ("Lim-Dûl the Necromancer", "lim-dul-the-necromancer"),
    ("Éowyn, Lady of Rohan", "eowyn-lady-of-rohan"),
    ("Ratonhnhaké꞉ton", "ratonhnhaketon"),  # modifier-letter colon
    ("Ratonhnhaké:ton", "ratonhnhaketon"),  # ASCII colon
    ("Minsc & Boo, Timeless Heroes", "minsc-boo-timeless-heroes"),
    ("Dr. Madison Li", "dr-madison-li"),
    ("Mr. House, President and CEO", "mr-house-president-and-ceo"),
    ("H.E.R.B.I.E.", "herbie"),
    ("U.S.Agent", "usagent"),
    ("Muad'Dib, Prophet Foretold", "muaddib-prophet-foretold"),
    ('"Name Sticker" Goblin', "name-sticker-goblin"),
    ("Esika, God of the Tree // The Prismatic Bridge", "esika-god-of-the-tree"),
    ("SP//dr, Piloted by Peni", "sp-dr-piloted-by-peni"),
    ("  Krenko,   Mob  Boss ", "krenko-mob-boss"),
    ("Thrasios, Triton Hero", "thrasios-triton-hero"),
    ("atraxa-praetors-voice", "atraxa-praetors-voice"),  # already a slug
    ("", ""),
]


@pytest.mark.parametrize("name,slug", SLUG_CASES)
def test_slugify(name, slug):
    assert edhrec.slugify(name) == slug


@pytest.mark.parametrize("name,_", SLUG_CASES)
def test_slugify_idempotent_and_url_safe(name, _):
    once = edhrec.slugify(name)
    assert edhrec.slugify(once) == once
    assert all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in once)
    assert not once.startswith("-") and "--" not in once


@pytest.mark.parametrize(
    "value,ok",
    [
        ("dragons", True),
        ("plus-one-counters", True),
        ("cedh", True),
        ("", False),
        ("../x", False),
        ("Dragons", False),
        ("a b", False),
        ("-lead", False),
        ("x" * 65, False),
        ("tag/../../x", False),
    ],
)
def test_scope_slug_validation(value, ok):
    assert edhrec.is_safe_scope_slug(value) is ok


def test_scope_url_never_interpolates_unsafe_values():
    url = edhrec._scope_url("Atraxa, Praetors' Voice", "../../etc", "nope")
    assert url == "https://json.edhrec.com/pages/commanders/atraxa-praetors-voice.json"
    url = edhrec._scope_url("the-ur-dragon", "dragons", "budget")
    assert url.endswith("/the-ur-dragon/dragons/budget.json")


def test_resolve_pairing_slug_tries_both_orders(fake_http):
    slug = edhrec.resolve_pairing_slug("Tymna the Weaver", "Thrasios, Triton Hero")
    assert slug == "thrasios-triton-hero-tymna-the-weaver"
    assert len(fake_http.edhrec_calls()) == 2


def test_fetch_classifies_errors(fake_http):
    data, err = edhrec.fetch_commander_scope("not-a-real-commander")
    assert data is None and err == edhrec.FETCH_NOT_FOUND
    fake_http.fail_hosts.add("edhrec.com")
    data, err = edhrec.fetch_commander_scope("atraxa-praetors-voice")
    assert data is None and err == edhrec.FETCH_NETWORK


def test_scope_fallback_recorded(fake_http):
    data, err = edhrec.fetch_commander_scope(
        "the-ur-dragon", tag="dragons", budget="budget"
    )
    assert err is None
    assert edhrec.served_scope(data) == ("", "")
    note = edhrec.scope_fallback_warning(data, tag="dragons", budget="budget")
    assert "theme 'dragons'" in note and "budget 'budget'" in note
