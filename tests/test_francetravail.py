"""Tests FranceTravailAdapter — OAuth2 + mapping + gestion d'erreurs."""

from unittest.mock import MagicMock, call, patch

import pytest

from offerlens.sources.francetravail import FranceTravailAdapter


def _mock_token_response(token: str = "tok_123") -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"access_token": token}
    return mock


def _mock_search_response(jobs: list[dict], status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"resultats": jobs}
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mock.raise_for_status.return_value = None
    return mock


def _make_job(**kwargs) -> dict:
    defaults = {
        "intitule": "Développeur Python",
        "entreprise": {"nom": "Tech SA"},
        "lieuTravail": {"libelle": "Lyon (69)"},
        "description": "Mission Python backend.",
        "origineOffre": {"urlOrigine": "https://ft.example.com/offre/123"},
        "id": "123FT456",
    }
    defaults.update(kwargs)
    return defaults


def test_search_fetches_token_then_calls_api():
    adapter = FranceTravailAdapter("client_id", "client_secret")
    with patch("offerlens.sources.francetravail.httpx.post") as mock_post, \
         patch("offerlens.sources.francetravail.httpx.get") as mock_get:
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_search_response([_make_job()])
        offers = adapter.search("python backend")
    mock_post.assert_called_once()
    mock_get.assert_called_once()
    assert len(offers) == 1


def test_search_returns_correct_raw_offer():
    adapter = FranceTravailAdapter("client_id", "client_secret")
    with patch("offerlens.sources.francetravail.httpx.post") as mock_post, \
         patch("offerlens.sources.francetravail.httpx.get") as mock_get:
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_search_response([_make_job()])
        offers = adapter.search("python")
    assert offers[0].source == "francetravail"
    assert offers[0].title == "Développeur Python"
    assert offers[0].company == "Tech SA"
    assert offers[0].location == "Lyon (69)"
    assert offers[0].url == "https://ft.example.com/offre/123"


def test_search_empty_results():
    adapter = FranceTravailAdapter("client_id", "client_secret")
    with patch("offerlens.sources.francetravail.httpx.post") as mock_post, \
         patch("offerlens.sources.francetravail.httpx.get") as mock_get:
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_search_response([])
        offers = adapter.search("python")
    assert offers == []


def test_search_handles_missing_fields():
    adapter = FranceTravailAdapter("client_id", "client_secret")
    with patch("offerlens.sources.francetravail.httpx.post") as mock_post, \
         patch("offerlens.sources.francetravail.httpx.get") as mock_get:
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_search_response([{}])
        offers = adapter.search("python")
    assert offers[0].title == ""
    assert offers[0].company == ""
    assert offers[0].url == ""


def test_oauth2_failure_raises():
    adapter = FranceTravailAdapter("bad_id", "bad_secret")
    with patch("offerlens.sources.francetravail.httpx.post") as mock_post:
        mock_post.return_value.raise_for_status.side_effect = Exception("401 Unauthorized")
        with pytest.raises(Exception):
            adapter.search("python")


def test_api_error_raises():
    adapter = FranceTravailAdapter("client_id", "client_secret")
    with patch("offerlens.sources.francetravail.httpx.post") as mock_post, \
         patch("offerlens.sources.francetravail.httpx.get") as mock_get:
        mock_post.return_value = _mock_token_response()
        mock_get.return_value = _mock_search_response([], status_code=503)
        with pytest.raises(Exception):
            adapter.search("python")
