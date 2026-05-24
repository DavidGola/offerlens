"""Adapter Remotive API — remote jobs, sans authentification."""

import re
from datetime import datetime

import httpx

from offerlens.sources.base import JobSourceAdapter, RawOffer

_BASE_URL = "https://remotive.com/api/remote-jobs"


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


class RemotiveAdapter:
    """Implémente JobSourceAdapter pour l'API Remotive (remote jobs, free, no auth)."""

    def search(self, query: str, limit: int = 50) -> list[RawOffer]:
        response = httpx.get(
            _BASE_URL,
            params={"search": query, "limit": limit},
            timeout=15,
        )
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        return [self._to_raw_offer(job) for job in jobs[:limit]]

    def fetch_by_url(self, url: str) -> RawOffer:
        raise NotImplementedError("RemotiveAdapter ne supporte pas fetch_by_url — utilisez search().")

    def _to_raw_offer(self, job: dict) -> RawOffer:
        posted_at = None
        if raw_date := job.get("published_at"):
            try:
                posted_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                pass
        return RawOffer(
            source="remotive",
            url=job.get("url", ""),
            title=job.get("title", ""),
            company=job.get("company_name", ""),
            location=job.get("candidate_required_location", ""),
            raw_content=_strip_html(job.get("description", "")),
            posted_at=posted_at,
        )


assert isinstance(RemotiveAdapter(), JobSourceAdapter)
