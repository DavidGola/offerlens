"""Pipeline LCEL de scoring — RawOffer → JobScore via RAG sur cv_chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel

from offerlens.llm import get_chat_model, get_embeddings
from offerlens.sources.base import RawOffer

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseChatModel


class JobScore(BaseModel):
    score: int
    explanation: str
    matched_skills: list[str]
    missing_skills: list[str]
    red_flags: list[str]


class ScoredOffer(BaseModel):
    offer: RawOffer
    job_score: JobScore
    offer_id: str = ""


_SCORING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Tu es un assistant qui évalue le matching entre un profil et une offre d'emploi.
Voici des extraits du CV du candidat :
{cv_context}

Évalue l'offre suivante et réponds avec un JSON structuré :
- score : entier de 0 à 5 (5 = match parfait)
- explanation : 2-3 phrases expliquant le score
- matched_skills : compétences du CV qui matchent l'offre
- missing_skills : compétences requises absentes du CV
- red_flags : signaux négatifs (surqualification, domaine éloigné, etc.)"""),
    ("human", "Offre : {offer_text}"),
])


def _build_offer_text(offer: RawOffer) -> str:
    return f"Titre : {offer.title}\nEntreprise : {offer.company}\nLocalisation : {offer.location}\n\n{offer.raw_content}"


class OfferScorer:
    """Score des offres contre le CV via RAG + LLM. Injectable pour les tests."""

    def __init__(
        self,
        *,
        llm: BaseChatModel | None = None,
        embeddings: Embeddings | None = None,
        cv_retriever: Callable[[str], str] | None = None,
        max_concurrency: int = 2,
    ):
        self._embeddings = embeddings or get_embeddings()
        self._llm = (llm or get_chat_model()).with_structured_output(JobScore)
        self._cv_retriever = cv_retriever or self._default_cv_retriever
        self._max_concurrency = max_concurrency
        self._chain = (
            RunnablePassthrough.assign(cv_context=lambda x: self._cv_retriever(x["offer_text"]))
            | _SCORING_PROMPT
            | self._llm
        )

    def _default_cv_retriever(self, offer_text: str) -> str:
        from offerlens.storage.firestore import search_cv_chunks

        embedding = self._embeddings.embed_query(offer_text)
        chunks = search_cv_chunks(embedding, limit=5)
        return "\n---\n".join(chunks)

    def score(self, offer: RawOffer) -> ScoredOffer:
        offer_text = _build_offer_text(offer)
        job_score: JobScore = self._chain.invoke({"offer_text": offer_text})
        return ScoredOffer(offer=offer, job_score=job_score)

    def score_batch(self, offers: list[RawOffer]) -> list[ScoredOffer]:
        if not offers:
            return []
        inputs = [{"offer_text": _build_offer_text(o)} for o in offers]
        job_scores: list[JobScore] = self._chain.batch(
            inputs, config={"max_concurrency": self._max_concurrency}
        )
        return [
            ScoredOffer(offer=offer, job_score=score)
            for offer, score in zip(offers, job_scores)
        ]
