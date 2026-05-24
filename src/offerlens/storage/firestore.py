"""Client Firestore et repositories — cv_chunks, offers, scan_runs, preferences."""

from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from offerlens.config import settings


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


def save_scored_offer(offer_data: dict) -> str:
    """Persiste une offre scorée dans Firestore. Retourne l'ID du document."""
    db = get_client()
    ref = db.collection("offers").document()
    ref.set(offer_data)
    return ref.id


def get_top_offers(limit: int = 5) -> list[dict]:
    """Retourne les `limit` meilleures offres non vues, triées par score décroissant."""
    db = get_client()
    docs = (
        db.collection("offers")
        .where("status", "==", "new")
        .where("seen_at", "==", None)
        .order_by("score", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .get()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def mark_offers_seen(offer_ids: list[str]) -> None:
    """Marque les offres comme vues."""
    from datetime import datetime, timezone
    db = get_client()
    for offer_id in offer_ids:
        db.collection("offers").document(offer_id).update({"seen_at": datetime.now(timezone.utc)})
