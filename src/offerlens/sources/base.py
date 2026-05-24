"""Interface JobSourceAdapter (Protocol) et modèle RawOffer (Pydantic)."""

from datetime import datetime
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


@runtime_checkable
class JobSourceAdapter(Protocol):
    def search(self, query: str, limit: int = 50) -> list[RawOffer]: ...
    def fetch_by_url(self, url: str) -> RawOffer: ...
