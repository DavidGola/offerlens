"""Pipeline LCEL de scoring — RawOffer → JobScore via RAG sur cv_chunks."""

from datetime import datetime, timezone

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel

from offerlens.llm import get_chat_model, get_embeddings
from offerlens.sources.base import RawOffer
from offerlens.storage.firestore import save_scored_offer, search_cv_chunks


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


def _retrieve_cv_chunks(offer_text: str) -> str:
    embedding = get_embeddings().embed_query(offer_text)
    chunks = search_cv_chunks(embedding, limit=5)
    return "\n---\n".join(chunks)


def _build_offer_text(offer: RawOffer) -> str:
    return f"Titre : {offer.title}\nEntreprise : {offer.company}\nLocalisation : {offer.location}\n\n{offer.raw_content}"


def score_offer(offer: RawOffer) -> ScoredOffer:
    offer_text = _build_offer_text(offer)
    llm = get_chat_model().with_structured_output(JobScore)

    chain = (
        RunnablePassthrough.assign(cv_context=lambda x: _retrieve_cv_chunks(x["offer_text"]))
        | _SCORING_PROMPT
        | llm
    )

    job_score: JobScore = chain.invoke({"offer_text": offer_text})

    offer_data = {
        **offer.model_dump(),
        "score": job_score.score,
        "explanation": job_score.explanation,
        "matched_skills": job_score.matched_skills,
        "missing_skills": job_score.missing_skills,
        "red_flags": job_score.red_flags,
        "scanned_at": datetime.now(timezone.utc),
    }
    offer_id = save_scored_offer(offer_data, source=offer.source, url=offer.url)

    return ScoredOffer(offer=offer, job_score=job_score, offer_id=offer_id)
