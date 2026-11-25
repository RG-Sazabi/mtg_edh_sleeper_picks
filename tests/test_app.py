"""Flask test-client smoke tests (offline: fake HTTP + fixture bulk store)."""

import html
import json
import re

import pytest

import app as app_module
from tests.helpers import edhrec_page, slept_on_grids

TYPE_SECTIONS = {
    "Creature",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Artifact",
    "Land",
    "Planeswalker",
}


@pytest.fixture
def client(loaded_bulk, fake_http):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _text(resp) -> str:
    return resp.get_data(as_text=True)


def _warning(page: str) -> str:
    m = re.search(r'<div class="data-warning" role="alert">(.*?)</div>', page, re.S)
    return html.unescape(m.group(1)) if m else ""


def _footer(page: str) -> str:
    m = re.search(r'<footer class="data-age[^"]*">(.*?)</footer>', page, re.S)
    return " ".join(m.group(1).split()) if m else ""


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    page = _text(resp)
    assert 'name="commander"' in page and 'name="archidekt_url"' in page
    assert "Card data as of 2026-11-25" in _footer(page)


def test_commanders_json(client):
    resp = client.get("/commanders.json")
    assert resp.status_code == 200
    names = resp.get_json()
    assert "Atraxa, Praetors' Voice" in names and "The Ur-Dragon" in names
    assert (
        "Urza, Planeswalker" not in names
        and "Brisela, Voice of Nightmares" not in names
    )
    assert names == sorted(names, key=str.casefold)


def test_partners_endpoint(client):
    data = client.get("/partners?name=Pir, Imaginative Rascal").get_json()
    assert data == {
        "eligible": True,
        "kind": "partner_with",
        "partners": ["Toothy, Imaginary Friend"],
    }


@pytest.mark.parametrize(
    "slug",
    [
        "atraxa-praetors-voice",
        "the-ur-dragon",
        "thrasios-triton-hero-tymna-the-weaver",
    ],
)
def test_commander_page_renders(client, fake_http, slug):
    resp = client.get(f"/commander/{slug}")
    assert resp.status_code == 200
    page = _text(resp)
    assert _warning(page) == ""
    assert "Card data as of 2026-11-25" in _footer(page)
    grids = slept_on_grids(page)
    assert len(grids) == 1 + len(TYPE_SECTIONS)
    for attrs, names in grids:
        assert names, f"empty Slept On grid: {attrs}"
    # Top 10 grid carries the fixed-N cap; commanders never appear in it.
    top_attrs, top_names = grids[0]
    assert 'data-fixed-n="10"' in top_attrs
    data = edhrec_page(slug)["container"]["json_dict"]
    for cm in data["card"].get("names") or [data["card"]["name"]]:
        assert all(cm not in names for _, names in grids)
    # Scoring view reused for the base scope: one EDHRec request per page.
    assert len(fake_http.edhrec_calls()) == 1


def test_top10_matches_golden(client):
    from tests.helpers import FIXTURES

    golden = json.loads(
        (FIXTURES / "golden_top10_atraxa.json").read_text(encoding="utf-8")
    )["top10"]
    page = _text(client.get("/commander/atraxa-praetors-voice"))
    _, top_names = slept_on_grids(page)[0]
    assert top_names[:10] == [c["name"] for c in golden]


def test_edhrec_tab_groups_meta_cards_by_type(client):
    page = _text(client.get("/commander/the-ur-dragon"))
    section = page.split('<section id="edhrec-section"', 1)[1].split("</section>")[0]
    headings = re.findall(r"<h3>(.*?)</h3>", section)
    # Featured rows first, then type groups; "High Lift Cards" only as a row.
    assert headings[:3] == ["New Cards", "Top Cards", "High Lift Cards"]
    assert headings.count("High Lift Cards") == 1
    type_groups = headings[3:]
    assert "Creatures" in type_groups and "Other" not in type_groups
    assert not {"New Cards", "Top Cards", "High Lift Cards"} & set(type_groups)
    # Every Top Cards card also sits in a type group (rendered twice in the tab).
    data = edhrec_page("the-ur-dragon")["container"]["json_dict"]
    top = [
        cv["name"]
        for cl in data["cardlists"]
        if cl["tag"] == "topcards"
        for cv in cl["cardviews"]
    ]
    for name in top:
        assert section.count(f'data-name="{html.escape(name)}"') == 2, name


def test_nonsense_slug_is_friendly_404(client):
    resp = client.get("/commander/not-a-real-commander-xyz")
    assert resp.status_code == 404
    assert "not found on EDHRec" in _text(resp)


def test_network_failure_is_502(client, fake_http):
    fake_http.fail_hosts.add("edhrec.com")
    resp = client.get("/commander/atraxa-praetors-voice")
    assert resp.status_code == 502
    assert "Couldn't reach EDHRec" in html.unescape(_text(resp))


@pytest.mark.parametrize(
    "query,warning",
    [
        ("deck=abc", "Ignored an invalid Archidekt deck id."),
        ("deck=12%C2%B3", "Ignored an invalid Archidekt deck id."),
        ("tag=../../etc", "Ignored an invalid theme."),
        ("tag=Dragons%20Pls", "Ignored an invalid theme."),
        ("bracket=<script>", "Ignored an invalid bracket."),
        ("budget=free", "Ignored an invalid budget."),
    ],
)
def test_invalid_params_banner_no_fetch(client, fake_http, query, warning):
    resp = client.get(f"/commander/atraxa-praetors-voice?{query}")
    assert resp.status_code == 200
    assert warning in _warning(_text(resp))
    assert not any("archidekt" in u for u in fake_http.calls)
    assert fake_http.edhrec_calls() == [
        "https://json.edhrec.com/pages/commanders/atraxa-praetors-voice.json"
    ]


def test_unfetchable_theme_falls_back_with_banner(client):
    resp = client.get("/commander/the-ur-dragon?tag=dragons")
    assert resp.status_code == 200
    assert "Couldn't load EDHRec data for theme 'dragons'" in _warning(_text(resp))


def test_renamed_deck_count_shows_banner_not_500(client, fake_http):
    payload = edhrec_page("atraxa-praetors-voice")
    for cl in payload["container"]["json_dict"]["cardlists"]:
        for cv in cl["cardviews"]:
            cv["deck_count"] = cv.pop("num_decks")
    fake_http.edhrec_payloads["atraxa-praetors-voice"] = payload
    resp = client.get("/commander/atraxa-praetors-voice")
    assert resp.status_code == 200
    assert "EDHRec data looks off" in _warning(_text(resp))
    assert "inclusion rate" in _warning(_text(resp))


def test_unknown_list_tag_shows_banner(client, fake_http):
    payload = edhrec_page("the-ur-dragon")
    payload["container"]["json_dict"]["cardlists"][2]["tag"] = "spicycards"
    fake_http.edhrec_payloads["the-ur-dragon"] = payload
    resp = client.get("/commander/the-ur-dragon")
    assert resp.status_code == 200
    assert "unrecognised EDHRec card list(s): spicycards" in _warning(_text(resp))


def test_empty_page_is_friendly_not_500(client, fake_http):
    payload = edhrec_page("atraxa-praetors-voice")
    payload["container"]["json_dict"]["cardlists"] = []
    fake_http.edhrec_payloads["atraxa-praetors-voice"] = payload
    resp = client.get("/commander/atraxa-praetors-voice")
    assert resp.status_code == 404
    assert "No card data found" in _text(resp)


def test_missing_commander_card_is_502(client, fake_http):
    payload = edhrec_page("atraxa-praetors-voice")
    del payload["container"]["json_dict"]["card"]["name"]
    fake_http.edhrec_payloads["atraxa-praetors-voice"] = payload
    resp = client.get("/commander/atraxa-praetors-voice")
    assert resp.status_code == 502
    assert "unexpected format" in _text(resp)


def test_deck_tab(client, fake_http):
    resp = client.get("/commander/thrasios-triton-hero-tymna-the-weaver?deck=1727139")
    assert resp.status_code == 200
    page = _text(resp)
    section = page.split('<section id="deck-section"', 1)[1].split("</section>")[0]
    assert len(re.findall(r'<div class="card-item"', section)) == 100
    assert "The 100 cards in your linked Archidekt deck" in section
    assert fake_http.calls.count("https://archidekt.com/api/decks/1727139/") == 1


def test_unreadable_deck_renders_without_tab(client):
    resp = client.get("/commander/atraxa-praetors-voice?deck=999")
    assert resp.status_code == 200
    assert 'id="deck-section"' not in _text(resp)


@pytest.mark.parametrize(
    "name,slug",
    [
        ("Lim-Dûl the Necromancer", "lim-dul-the-necromancer"),
        ("Dr. Madison Li", "dr-madison-li"),
        ("Mr. House, President and CEO", "mr-house-president-and-ceo"),
        ("Ratonhnhaké꞉ton", "ratonhnhaketon"),
        ("Esika, God of the Tree // The Prismatic Bridge", "esika-god-of-the-tree"),
    ],
)
def test_search_form_redirects_to_slug(client, name, slug):
    resp = client.post("/", data={"commander": name})
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/commander/{slug}"


def test_partner_search_resolves_canonical_order(client):
    resp = client.post(
        "/", data={"commander": "Tymna the Weaver", "partner": "Thrasios, Triton Hero"}
    )
    assert (
        resp.headers["Location"] == "/commander/thrasios-triton-hero-tymna-the-weaver"
    )


def test_archidekt_form_redirects_with_deck(client):
    resp = client.post(
        "/", data={"archidekt_url": "https://archidekt.com/decks/1727139/whatever"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == (
        "/commander/thrasios-triton-hero-tymna-the-weaver?deck=1727139"
    )


def test_archidekt_form_bad_url(client, fake_http):
    resp = client.post("/", data={"archidekt_url": "https://evil.com/decks/1"})
    assert resp.status_code == 400
    assert fake_http.calls == []
