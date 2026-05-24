"""Adapter Adzuna API — agrégateur multi-sources, free tier."""

import httpx

from offerlens.sources.base import JobSourceAdapter, RawOffer

_BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaAdapter:
    """Implémente JobSourceAdapter pour l'API Adzuna."""

    def __init__(self, app_id: str, api_key: str, country: str = "fr"):
        self._app_id = app_id
        self._api_key = api_key
        self._country = country

    def search(self, query: str, limit: int = 50) -> list[RawOffer]:
        response = httpx.get(
            f"{_BASE_URL}/{self._country}/search/1",
            params={
                "app_id": self._app_id,
                "app_key": self._api_key,
                "what": query,
                "results_per_page": min(limit, 50),
                "content-type": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
        jobs = response.json().get("results", [])
        return [self._to_raw_offer(job) for job in jobs[:limit]]

    def _to_raw_offer(self, job: dict) -> RawOffer:
        return RawOffer(
            source="adzuna",
            url=job.get("redirect_url", ""),
            title=job.get("title", ""),
            company=job.get("company", {}).get("display_name", ""),
            location=job.get("location", {}).get("display_name", ""),
            raw_content=job.get("description", ""),
        )


assert isinstance(AdzunaAdapter("x", "y"), JobSourceAdapter)
