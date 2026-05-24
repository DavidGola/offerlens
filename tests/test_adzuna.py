"""Tests AdzunaAdapter — mapping et gestion d'erreurs."""

from unittest.mock import MagicMock, patch

import pytest

from offerlens.sources.adzuna import AdzunaAdapter


def _make_job(**kwargs) -> dict:
    defaults = {
        "title": "Python Backend Engineer",
        "redirect_url": "https://adzuna.fr/job/123",
        "company": {"display_name": "Acme Corp"},
        "location": {"display_name": "Paris, Île-de-France"},
        "description": "We're looking for a Python dev.",
    }
    defaults.update(kwargs)
    return defaults


def _mock_response(jobs: list[dict], status_code: int = 200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"results": jobs}
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mock.raise_for_status.return_value = None
    return mock


def test_search_returns_raw_offers():
    adapter = AdzunaAdapter("app_id", "api_key")
    with patch("offerlens.sources.adzuna.httpx.get") as mock_get:
        mock_get.return_value = _mock_response([_make_job()])
        offers = adapter.search("python backend", limit=10)
    assert len(offers) == 1
    assert offers[0].source == "adzuna"
    assert offers[0].title == "Python Backend Engineer"
    assert offers[0].company == "Acme Corp"
    assert offers[0].location == "Paris, Île-de-France"
    assert offers[0].url == "https://adzuna.fr/job/123"


def test_search_empty_results():
    adapter = AdzunaAdapter("app_id", "api_key")
    with patch("offerlens.sources.adzuna.httpx.get") as mock_get:
        mock_get.return_value = _mock_response([])
        offers = adapter.search("python backend")
    assert offers == []


def test_search_respects_limit():
    adapter = AdzunaAdapter("app_id", "api_key")
    jobs = [_make_job(title=f"Job {i}") for i in range(10)]
    with patch("offerlens.sources.adzuna.httpx.get") as mock_get:
        mock_get.return_value = _mock_response(jobs)
        offers = adapter.search("python", limit=3)
    assert len(offers) == 3


def test_search_handles_missing_fields():
    adapter = AdzunaAdapter("app_id", "api_key")
    with patch("offerlens.sources.adzuna.httpx.get") as mock_get:
        mock_get.return_value = _mock_response([{}])
        offers = adapter.search("python")
    assert offers[0].title == ""
    assert offers[0].company == ""
    assert offers[0].url == ""


def test_search_raises_on_http_error():
    adapter = AdzunaAdapter("app_id", "api_key")
    with patch("offerlens.sources.adzuna.httpx.get") as mock_get:
        mock_get.return_value = _mock_response([], status_code=401)
        with pytest.raises(Exception):
            adapter.search("python")
