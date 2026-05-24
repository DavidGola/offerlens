"""Interface JobSourceAdapter (Protocol) et modèle RawOffer (Pydantic)."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class RawOffer(BaseModel):
    source: str
    url: str
    title: str
    company: str
    raw_content: str
    location: str = ""
    posted_at: datetime | None = None


_FRESHNESS_WINDOWS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def filter_by_freshness(offers: list[RawOffer], freshness: str) -> list[RawOffer]:
    """Retourne les offres publiées dans la fenêtre de temps. posted_at=None → fraîche."""
    if freshness not in _FRESHNESS_WINDOWS:
        raise ValueError(f"freshness invalide : '{freshness}'. Valeurs acceptées : {list(_FRESHNESS_WINDOWS)}")
    window = _FRESHNESS_WINDOWS[freshness]
    cutoff = datetime.now(timezone.utc) - window
    return [
        o for o in offers
        if o.posted_at is None or o.posted_at >= cutoff
    ]


def dedup_offers(offers: list[RawOffer]) -> list[RawOffer]:
    """Dédoublonne par hash sha256(normalize(title) + normalize(company)). First wins."""
    seen: set[str] = set()
    result: list[RawOffer] = []
    for offer in offers:
        key = hashlib.sha256(
            (offer.title.lower().strip() + offer.company.lower().strip()).encode()
        ).hexdigest()
        if key not in seen:
            seen.add(key)
            result.append(offer)
    return result


_EXCLUDED_TITLE_KEYWORDS = {"stage", "alternance", "alternant", "stagiaire", "apprenti", "apprentissage", "intern", "internship"}


def filter_contract_type(offers: list[RawOffer]) -> list[RawOffer]:
    """Exclut les offres de stage et d'alternance détectées par mots-clés dans le titre."""
    def _is_excluded(title: str) -> bool:
        words = title.lower().split()
        return any(w.strip("/-(),") in _EXCLUDED_TITLE_KEYWORDS for w in words)

    return [o for o in offers if not _is_excluded(o.title)]


@runtime_checkable
class JobSourceAdapter(Protocol):
    def search(self, query: str, limit: int = 50) -> list[RawOffer]: ...
