"""Tests de la purge automatique des offres > 30 jours."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

from typer.testing import CliRunner

from offerlens.cli import app


def _make_doc(scanned_at: datetime) -> MagicMock:
    doc = MagicMock()
    doc.to_dict.return_value = {"scanned_at": scanned_at}
    return doc


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── purge_old_offers supprime les offres périmées ────────────────────────────

def test_purge_deletes_offers_older_than_threshold():
    """Les offres avec scanned_at > 30 jours sont supprimées."""
    old_doc = _make_doc(_now() - timedelta(days=31))
    old_doc.reference = MagicMock()

    mock_query = MagicMock()
    mock_query.where.return_value.stream.return_value = [old_doc]

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value = mock_query
        from offerlens.storage.firestore import purge_old_offers
        purge_old_offers(days=30)

    old_doc.reference.delete.assert_called_once()


def test_purge_does_not_delete_recent_offers():
    """Les offres récentes (< 30 jours) ne sont pas supprimées."""
    recent_doc = _make_doc(_now() - timedelta(days=10))
    recent_doc.reference = MagicMock()

    mock_query = MagicMock()
    mock_query.where.return_value.stream.return_value = []  # aucun résultat pour < seuil

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value = mock_query
        from offerlens.storage.firestore import purge_old_offers
        purge_old_offers(days=30)

    recent_doc.reference.delete.assert_not_called()


def test_purge_no_error_on_empty_collection():
    """purge_old_offers ne lève pas d'erreur si la collection est vide."""
    mock_query = MagicMock()
    mock_query.where.return_value.stream.return_value = []

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value = mock_query
        from offerlens.storage.firestore import purge_old_offers
        purge_old_offers(days=30)  # ne doit pas lever d'exception


def test_purge_filters_by_scanned_at_not_posted_at():
    """La purge utilise scanned_at, pas posted_at."""
    mock_query = MagicMock()
    mock_query.where.return_value.stream.return_value = []

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value = mock_query
        from offerlens.storage.firestore import purge_old_offers
        purge_old_offers(days=30)

    where_call = mock_query.where.call_args
    assert where_call[0][0] == "scanned_at"


# ── scan appelle purge_old_offers au début ───────────────────────────────────

runner = CliRunner()


def test_scan_calls_purge_before_scoring():
    """La commande scan appelle purge_old_offers avant de scorer les offres."""
    call_order = []

    def fake_purge(days=30):
        call_order.append("purge")

    mock_scored = MagicMock()
    mock_scored.job_score.score = 3
    mock_scored.offer.title = "Dev"
    mock_scored.offer.company = "ACME"
    mock_scored.job_score.matched_skills = []

    def fake_score(offer):
        call_order.append("score")
        return mock_scored

    with (
        patch("offerlens.sources.remotive.RemotiveAdapter") as MockAdapter,
        patch("offerlens.pipeline.scoring.score_offer", side_effect=fake_score),
        patch("offerlens.storage.firestore.purge_old_offers", side_effect=fake_purge),
    ):
        MockAdapter.return_value.search.return_value = [MagicMock(title="Dev")]
        runner.invoke(app, ["scan"])

    assert call_order[0] == "purge", "purge doit être appelé avant le scoring"
