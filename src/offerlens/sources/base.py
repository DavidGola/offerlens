"""Interface JobSourceAdapter (Protocol) et modèle RawOffer (Pydantic)."""

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


@runtime_checkable
class JobSourceAdapter(Protocol):
    def search(self, query: str, limit: int = 50) -> list[RawOffer]: ...
    def fetch_by_url(self, url: str) -> RawOffer: ...
