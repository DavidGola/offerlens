"""Adapter France Travail API — OAuth2 Client Credentials + recherche d'offres."""

import time

import httpx

from offerlens.sources.base import JobSourceAdapter, RawOffer

_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
_SCOPE = "api_offresdemploiv2 o2dsoffre"
_TOKEN_MARGIN_SECONDS = 60


def _fetch_token(client_id: str, client_secret: str) -> tuple[str, float]:
    response = httpx.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": _SCOPE,
        },
        params={"realm": "/partenaire"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    expires_at = time.monotonic() + data.get("expires_in", 1500) - _TOKEN_MARGIN_SECONDS
    return data["access_token"], expires_at


class FranceTravailAdapter:
    """Implémente JobSourceAdapter pour l'API France Travail (ex-Pôle Emploi)."""

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at: float = 0

    def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        self._token, self._token_expires_at = _fetch_token(self._client_id, self._client_secret)
        return self._token

    def search(self, query: str, limit: int = 50) -> list[RawOffer]:
        token = self._get_token()
        response = httpx.get(
            _SEARCH_URL,
            params={"motsCles": query, "range": f"0-{min(limit, 149) - 1}"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        jobs = response.json().get("resultats", [])
        return [self._to_raw_offer(job) for job in jobs[:limit]]

    def _to_raw_offer(self, job: dict) -> RawOffer:
        lieu = job.get("lieuTravail", {})
        location = lieu.get("libelle", "")
        entreprise = job.get("entreprise", {})
        description = job.get("description", "")
        return RawOffer(
            source="francetravail",
            url=job.get("origineOffre", {}).get("urlOrigine", job.get("id", "")),
            title=job.get("intitule", ""),
            company=entreprise.get("nom", ""),
            location=location,
            raw_content=description,
        )


assert isinstance(FranceTravailAdapter("x", "y"), JobSourceAdapter)
