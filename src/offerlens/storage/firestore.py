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
    """Retourne les `limit` meilleures offres triées par score décroissant."""
    db = get_client()
    docs = (
        db.collection("offers")
        .order_by("score", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .get()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def purge_old_offers(days: int = 30) -> None:
    """Supprime les offres dont scanned_at est antérieur à `days` jours."""
    from datetime import datetime, timedelta, timezone
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    db = get_client()
    old_docs = db.collection("offers").where("scanned_at", "<", threshold).stream()
    for doc in old_docs:
        doc.reference.delete()


def mark_offers_seen(offer_ids: list[str]) -> None:
    """Marque les offres comme vues."""
    from datetime import datetime, timezone
    db = get_client()
    for offer_id in offer_ids:
        db.collection("offers").document(offer_id).update({"seen_at": datetime.now(timezone.utc)})


def count_today_offers() -> int:
    """Compte les offres dont scanned_at est aujourd'hui (UTC)."""
    from datetime import datetime, timezone
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
