"""Tests du source registry — découverte et validation des credentials."""

from unittest.mock import patch

import pytest

from offerlens.sources.registry import get_sources


def _settings(**kwargs):
    defaults = dict(
        adzuna_app_id="",
        adzuna_api_key="",
        ft_client_id="",
        ft_client_secret="",
    )
    defaults.update(kwargs)
    return defaults


def test_only_remotive_when_no_optional_credentials():
    with patch("offerlens.sources.registry.settings") as mock:
        mock.adzuna_app_id = ""
        mock.adzuna_api_key = ""
        mock.ft_client_id = ""
        mock.ft_client_secret = ""
        sources = get_sources()
    assert len(sources) == 1
    assert sources[0].__class__.__name__ == "RemotiveAdapter"


def test_all_three_sources_when_all_credentials_set():
    with patch("offerlens.sources.registry.settings") as mock:
        mock.adzuna_app_id = "app123"
        mock.adzuna_api_key = "key456"
        mock.ft_client_id = "ftid"
        mock.ft_client_secret = "ftsecret"
        sources = get_sources()
    assert len(sources) == 3
    names = {s.__class__.__name__ for s in sources}
    assert names == {"RemotiveAdapter", "AdzunaAdapter", "FranceTravailAdapter"}


def test_partial_adzuna_config_raises():
    with patch("offerlens.sources.registry.settings") as mock:
        mock.adzuna_app_id = "app123"
        mock.adzuna_api_key = ""
        mock.ft_client_id = ""
        mock.ft_client_secret = ""
        with pytest.raises(ValueError, match="ADZUNA"):
            get_sources()


def test_partial_francetravail_config_raises():
    with patch("offerlens.sources.registry.settings") as mock:
        mock.adzuna_app_id = ""
        mock.adzuna_api_key = ""
        mock.ft_client_id = "ftid"
        mock.ft_client_secret = ""
        with pytest.raises(ValueError, match="FT_"):
            get_sources()


def test_source_filter_returns_only_matching():
    with patch("offerlens.sources.registry.settings") as mock:
        mock.adzuna_app_id = "app123"
        mock.adzuna_api_key = "key456"
        mock.ft_client_id = ""
        mock.ft_client_secret = ""
        sources = get_sources(source_filter="adzuna")
    assert len(sources) == 1
    assert sources[0].__class__.__name__ == "AdzunaAdapter"


def test_source_filter_unknown_raises():
    with patch("offerlens.sources.registry.settings") as mock:
        mock.adzuna_app_id = ""
        mock.adzuna_api_key = ""
        mock.ft_client_id = ""
        mock.ft_client_secret = ""
        with pytest.raises(ValueError, match="Source inconnue"):
            get_sources(source_filter="linkedin")
