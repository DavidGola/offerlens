"""Adapter URL paste — httpx + JSON-LD extraction, fallback Claude → RawOffer."""

import json
import re

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from offerlens.llm import get_chat_model
from offerlens.sources.base import RawOffer

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

_EXTRACT_PROMPT = """Tu reçois le contenu texte d'une page d'offre d'emploi.
Extrait les informations suivantes en JSON :
- title : intitulé du poste
- company : nom de l'entreprise
- location : lieu (ville, remote, hybride...)
- content : description complète du poste (compétences, missions, profil recherché)

Si une information est absente, utilise une chaîne vide.
Réponds uniquement avec le JSON, sans explication."""


class _ExtractedOffer(BaseModel):
    title: str
    company: str
    location: str
    content: str


def _extract_jsonld(html: str) -> dict | None:
    """Tente d'extraire un JobPosting depuis les balises JSON-LD de la page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            if isinstance(data, list):
                data = next((d for d in data if d.get("@type") == "JobPosting"), None)
            if data and data.get("@type") == "JobPosting":
                return data
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def _jsonld_to_offer(url: str, data: dict) -> RawOffer:
    description = re.sub(r"<[^>]+>", " ", data.get("description", ""))
    return RawOffer(
        source="url",
        url=url,
        title=data.get("title", ""),
        company=data.get("hiringOrganization", {}).get("name", ""),
        location=data.get("jobLocation", {}).get("address", {}).get("addressLocality", ""),
        raw_content=description,
    )


class URLFetchAdapter:
    def __init__(self):
        self._llm = get_chat_model().with_structured_output(_ExtractedOffer)

    def fetch_by_url(self, url: str) -> RawOffer:
        response = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=15)
        response.raise_for_status()
        html = response.text

        jsonld = _extract_jsonld(html)
        if jsonld:
            return _jsonld_to_offer(url, jsonld)

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)[:8000]
        extracted = self._llm.invoke(f"{_EXTRACT_PROMPT}\n\n{text}")
        return RawOffer(
            source="url",
            url=url,
            title=extracted.title,
            company=extracted.company,
            location=extracted.location,
            raw_content=extracted.content,
        )

    def search(self, query: str, limit: int = 50) -> list[RawOffer]:
        raise NotImplementedError("URLFetchAdapter ne supporte pas la recherche — utilisez fetch_by_url.")
