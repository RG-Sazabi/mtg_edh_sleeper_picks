"""
Shared offline test fixtures.

Every test except those marked ``live`` runs with the network blocked: any real
HTTP request raises. Tests that need EDHRec / Archidekt / Scryfall responses get
them from ``fake_http``, which serves the recorded JSON under ``tests/fixtures/``.

The bulk store is pointed at a *copy* of ``tests/fixtures/bulk/`` (a few thousand
real Scryfall cards in the same gzip JSON-Lines format the app downloads), never
at the real ``cache/``. Two module constants are patched for that, both
deliberate: ``CACHE_DIR`` (where the store reads from) and the ``_MIN_CARDS`` /
``_MIN_TAGGED`` sanity floors, which are sized for the full ~37k-card catalog and
would (correctly) reject the small sample.
"""

import copy
import shutil
from pathlib import Path

import pytest
import requests

from services import bulk, scryfall
from tests.helpers import (
    BULK_FIXTURES,
    EDHREC_PAGES,
    PAIRING_REDIRECTS,
    cached_json,
    edhrec_page,
)

# Floors used for the fixture sample (real floors: 10_000 cards / 1_000 tagged).
SAMPLE_MIN_CARDS = 1_000
SAMPLE_MIN_TAGGED = 500

# --------------------------------------------------------------------------
# Network guard + fake HTTP
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    """Fail loudly on any real HTTP request outside ``live`` tests."""
    if request.node.get_closest_marker("live"):
        return

    def _blocked(self, method, url, *args, **kwargs):
        raise AssertionError(f"real network access in an offline test: {method} {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", _blocked)


class FakeResponse:
    def __init__(self, status=200, payload=None, content=b"", headers=None):
        self.status_code = status
        self._payload = payload
        self.content = content
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeHTTP:
    """
    Stand-in for ``requests.get`` serving the recorded fixtures. ``calls`` lists
    every URL requested. Set ``edhrec_payloads[slug]`` to serve a modified page,
    ``fail_hosts`` to raise ConnectionError for a host, or ``routes[url]`` to a
    FakeResponse / callable for anything else.
    """

    EDHREC = "https://json.edhrec.com/pages/commanders/"

    def __init__(self):
        self.calls: list[str] = []
        self.edhrec_payloads: dict[str, dict] = {}
        self.fail_hosts: set[str] = set()
        self.routes: dict = {}

    def __call__(self, url, params=None, headers=None, timeout=None, **kwargs):
        self.calls.append(url)
        for host in self.fail_hosts:
            if host in url:
                raise requests.ConnectionError(f"simulated network failure: {url}")
        if url in self.routes:
            route = self.routes[url]
            return route(url) if callable(route) else route
        if url.startswith(self.EDHREC):
            return self._edhrec(url[len(self.EDHREC) :])
        if url.startswith("https://archidekt.com/api/decks/"):
            deck_id = url.rstrip("/").rsplit("/", 1)[-1]
            if deck_id == "1727139":
                return FakeResponse(
                    payload=copy.deepcopy(cached_json("archidekt_1727139.json"))
                )
            return FakeResponse(404, {"detail": "Not found."})
        if url == "https://api.scryfall.com/bulk-data":
            return FakeResponse(
                payload=copy.deepcopy(cached_json("scryfall_bulk_data.json"))
            )
        if url.startswith("https://api.scryfall.com/cards/named"):
            return FakeResponse(404, {"object": "error", "status": 404})
        return FakeResponse(404, {"error": "not in fixtures"})

    def _edhrec(self, path: str):
        slug = path[: -len(".json")] if path.endswith(".json") else path
        if slug in self.edhrec_payloads:
            return FakeResponse(payload=copy.deepcopy(self.edhrec_payloads[slug]))
        if slug in EDHREC_PAGES:
            return FakeResponse(payload=edhrec_page(slug))
        if slug in PAIRING_REDIRECTS:
            # EDHRec answers a reversed pairing with a redirect stub, no container.
            return FakeResponse(
                payload={"redirect": f"/commanders/{PAIRING_REDIRECTS[slug]}"}
            )
        return FakeResponse(403, None)  # EDHRec's answer for unknown pages

    def edhrec_calls(self) -> list[str]:
        return [u for u in self.calls if u.startswith(self.EDHREC)]


@pytest.fixture
def fake_http(monkeypatch):
    fake = FakeHTTP()
    monkeypatch.setattr(requests, "get", fake)
    return fake


# --------------------------------------------------------------------------
# Bulk store on the fixture sample
# --------------------------------------------------------------------------


def copy_bulk_fixtures(dest: Path) -> Path:
    """Copy the sample bulk files to ``dest`` with fresh mtimes (copyfile, not
    copy2), so the store never considers them stale and never tries a refresh."""
    dest.mkdir(parents=True, exist_ok=True)
    for f in BULK_FIXTURES.iterdir():
        shutil.copyfile(f, dest / f.name)
    return dest


@pytest.fixture(scope="session")
def sample_store(tmp_path_factory):
    """One ``bulk._Store`` built from the fixture sample, shared by the session."""
    cache = copy_bulk_fixtures(tmp_path_factory.mktemp("bulk_cache"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(bulk, "CACHE_DIR", str(cache))
        mp.setattr(bulk, "_MIN_CARDS", SAMPLE_MIN_CARDS)
        mp.setattr(bulk, "_MIN_TAGGED", SAMPLE_MIN_TAGGED)
        store = bulk._build_store()
    return store


def _reset_bulk_state(monkeypatch, store, loaded, state, cache_dir):
    monkeypatch.setattr(bulk, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(bulk, "_MIN_CARDS", SAMPLE_MIN_CARDS)
    monkeypatch.setattr(bulk, "_MIN_TAGGED", SAMPLE_MIN_TAGGED)
    monkeypatch.setattr(bulk, "MAX_AGE_SECONDS", 10**9)
    monkeypatch.setattr(bulk, "_store", store)
    monkeypatch.setattr(bulk, "_loaded", loaded)
    monkeypatch.setattr(bulk, "_state", state)
    monkeypatch.setattr(bulk, "_last_error", "")
    monkeypatch.setattr(bulk, "_last_refresh_failed", False)
    monkeypatch.setattr(bulk, "_last_failed_attempt", 0.0)
    # Fresh per-test live-fallback caches.
    monkeypatch.setattr(scryfall, "_card_cache", {})
    monkeypatch.setattr(scryfall, "_miss_cache", {})
    monkeypatch.setattr(scryfall, "_cooldown_until", 0.0)


@pytest.fixture
def loaded_bulk(sample_store, monkeypatch, tmp_path):
    """The bulk module serving the fixture sample, as after a successful load.
    CACHE_DIR points at an empty temp dir so nothing can touch the real cache/."""
    _reset_bulk_state(monkeypatch, sample_store, True, "ready", tmp_path)
    return sample_store


@pytest.fixture
def empty_bulk(monkeypatch, tmp_path):
    """The bulk module in its never-loaded state, reading from ``tmp_path``."""
    _reset_bulk_state(monkeypatch, bulk._Store(), False, "empty", tmp_path)
    return tmp_path
