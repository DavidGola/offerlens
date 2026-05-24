"""Découverte des sources disponibles selon les credentials configurées."""

from offerlens.config import settings
from offerlens.sources.adzuna import AdzunaAdapter
from offerlens.sources.base import JobSourceAdapter
from offerlens.sources.francetravail import FranceTravailAdapter
from offerlens.sources.remotive import RemotiveAdapter

_VALID_SOURCES = {"remotive", "adzuna", "francetravail"}


def get_sources(source_filter: str | None = None) -> list[JobSourceAdapter]:
    """Retourne la liste des adapters disponibles selon les credentials configurées.

    Raises ValueError si la config d'une source est partielle, ou si source_filter est inconnu.
    """
    if source_filter is not None and source_filter not in _VALID_SOURCES:
        raise ValueError(f"Source inconnue : '{source_filter}'. Valeurs : {sorted(_VALID_SOURCES)}")

    _validate_partial_configs()

    adapters: list[JobSourceAdapter] = [RemotiveAdapter()]

    if settings.adzuna_app_id and settings.adzuna_api_key:
        adapters.append(AdzunaAdapter(settings.adzuna_app_id, settings.adzuna_api_key))

    if settings.ft_client_id and settings.ft_client_secret:
        adapters.append(FranceTravailAdapter(settings.ft_client_id, settings.ft_client_secret))

    if source_filter is not None:
        adapters = [a for a in adapters if a.__class__.__name__.lower().startswith(source_filter)]

    return adapters


def _validate_partial_configs() -> None:
    if bool(settings.adzuna_app_id) != bool(settings.adzuna_api_key):
        missing = "ADZUNA_API_KEY" if settings.adzuna_app_id else "ADZUNA_APP_ID"
        raise ValueError(f"Config Adzuna partielle — {missing} manquant.")

    if bool(settings.ft_client_id) != bool(settings.ft_client_secret):
        missing = "FT_CLIENT_SECRET" if settings.ft_client_id else "FT_CLIENT_ID"
        raise ValueError(f"Config France Travail partielle — {missing} manquant.")
