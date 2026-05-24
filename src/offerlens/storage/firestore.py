"""Client Firestore et repositories — cv_chunks, offers, scan_runs, preferences."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from offerlens.config import settings
from offerlens.pipeline.scoring import JobScore, ScoredOffer
from offerlens.sources.base import RawOffer


def _offer_doc_id(source: str, url: str) -> str:
    """Retourne un ID déterministe sha256(source + url)[:16]."""
    return hashlib.sha256(f"{source}{url}".encode()).hexdigest()[:16]


def _to_doc(scored: ScoredOffer) -> dict:
    return {
        **scored.offer.model_dump(),
        "score": scored.job_score.score,
        "explanation": scored.job_score.explanation,
        "matched_skills": scored.job_score.matched_skills,
        "missing_skills": scored.job_score.missing_skills,
        "red_flags": scored.job_score.red_flags,
        "scanned_at": datetime.now(timezone.utc),
    }


def _from_doc(doc_dict: dict, doc_id: str) -> ScoredOffer:
    offer = RawOffer(
        source=doc_dict.get("source", ""),
        url=doc_dict.get("url", ""),
        title=doc_dict.get("title", ""),
        company=doc_dict.get("company", ""),
        raw_content=doc_dict.get("raw_content", ""),
        location=doc_dict.get("location", ""),
        posted_at=doc_dict.get("posted_at"),
    )
    job_score = JobScore(
        score=doc_dict.get("score", 0),
        explanation=doc_dict.get("explanation", ""),
        matched_skills=doc_dict.get("matched_skills", []),
        missing_skills=doc_dict.get("missing_skills", []),
        red_flags=doc_dict.get("red_flags", []),
    )
    return ScoredOffer(offer=offer, job_score=job_score, offer_id=doc_id)


def get_client() -> firestore.Client:
    return firestore.Client(project=settings.gcp_project_id)


def search_cv_chunks(query_embedding: list[float], limit: int = 5) -> list[str]:
    """Retourne les `limit` chunks du CV les plus proches du vecteur requête."""
    db = get_client()
    results = (
        db.collection("cv_chunks")
        .find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_embedding),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit,
        )
        .get()
    )
    return [doc.to_dict().get("content", "") for doc in results]


def offer_exists(source: str, url: str) -> bool:
    """Retourne True si l'offre (source + url) est déjà en base."""
    db = get_client()
    return db.collection("offers").document(_offer_doc_id(source, url)).get().exists


def save_scored_offer(scored: ScoredOffer) -> str:
    """Persiste un ScoredOffer dans Firestore. Retourne l'ID du document.

    L'ID est déterministe (sha256(source+url)[:16]).
    Si le document existe déjà, l'écriture est ignorée (skip).
    """
    db = get_client()
    doc_id = _offer_doc_id(scored.offer.source, scored.offer.url)
    ref = db.collection("offers").document(doc_id)
    if ref.get().exists:
        return ref.id
    ref.set(_to_doc(scored))
    return ref.id


def get_top_offers(limit: int = 5) -> list[ScoredOffer]:
    """Retourne les `limit` meilleures offres triées par score décroissant."""
    db = get_client()
    docs = (
        db.collection("offers")
        .order_by("score", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .get()
    )
    return [_from_doc(doc.to_dict(), doc.id) for doc in docs]


def purge_old_offers(days: int = 30) -> None:
    """Supprime les offres dont scanned_at est antérieur à `days` jours."""
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    db = get_client()
    old_docs = db.collection("offers").where("scanned_at", "<", threshold).stream()
    for doc in old_docs:
        doc.reference.delete()


def count_today_offers() -> int:
    """Compte les offres dont scanned_at est aujourd'hui (UTC)."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    db = get_client()
    docs = (
        db.collection("offers")
        .where("scanned_at", ">=", day_start)
        .where("scanned_at", "<=", day_end)
        .stream()
    )
    return sum(1 for _ in docs)
