"""Tests du filtre fraîcheur — filter_by_freshness(offers, freshness_str)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from offerlens.cli import app
from offerlens.sources.base import RawOffer, filter_by_freshness


def _offer(posted_at: datetime | None, title: str = "Dev Python") -> RawOffer:
    return RawOffer(
        source="test",
        url="https://example.com",
        title=title,
        company="ACME",
        raw_content="Python backend remote",
        posted_at=posted_at,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Tracer bullet ────────────────────────────────────────────────────────────

def test_freshness_24h_keeps_recent_offer():
    recent = _offer(_now() - timedelta(hours=1))
    assert filter_by_freshness([recent], "24h") == [recent]


def test_freshness_24h_drops_old_offer():
    old = _offer(_now() - timedelta(days=2))
    assert filter_by_freshness([old], "24h") == []


# ── Fenêtres 7d et 30d ───────────────────────────────────────────────────────

def test_freshness_7d_keeps_offer_within_window():
    recent = _offer(_now() - timedelta(days=3))
    assert filter_by_freshness([recent], "7d") == [recent]


def test_freshness_7d_drops_offer_outside_window():
    old = _offer(_now() - timedelta(days=10))
    assert filter_by_freshness([old], "7d") == []


def test_freshness_30d_keeps_offer_within_window():
    recent = _offer(_now() - timedelta(days=20))
    assert filter_by_freshness([recent], "30d") == [recent]


def test_freshness_30d_drops_offer_outside_window():
    old = _offer(_now() - timedelta(days=31))
    assert filter_by_freshness([old], "30d") == []


# ── Offre sans posted_at ─────────────────────────────────────────────────────

def test_freshness_keeps_offer_without_date():
    """Offre sans date traitée comme fraîche (date = scan time)."""
    no_date = _offer(None)
    assert filter_by_freshness([no_date], "24h") == [no_date]


# ── Chaîne invalide ──────────────────────────────────────────────────────────

def test_freshness_invalid_string_raises():
    with pytest.raises(ValueError, match="freshness"):
        filter_by_freshness([_offer(_now())], "bad")


def test_freshness_invalid_string_2w_raises():
    with pytest.raises(ValueError, match="freshness"):
        filter_by_freshness([_offer(_now())], "2w")


# ── Mix d'offres ─────────────────────────────────────────────────────────────

def test_freshness_mixed_offers():
    recent = _offer(_now() - timedelta(hours=6), title="Recent")
    old = _offer(_now() - timedelta(days=5), title="Old")
    result = filter_by_freshness([recent, old], "24h")
    assert result == [recent]


# ── CLI wiring ───────────────────────────────────────────────────────────────

runner = CliRunner()


def test_scan_freshness_filters_before_scoring():
    """--freshness filtre les offres périmées avant l'appel à score_batch."""
    stale = _offer(_now() - timedelta(days=5), title="Stale Offer")
    mock_adapter = MagicMock()
    mock_adapter.search.return_value = [stale]

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[mock_adapter]),
        patch("offerlens.pipeline.scoring.OfferScorer.score_batch", return_value=[]) as mock_batch,
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=False),
    ):
        result = runner.invoke(app, ["scan", "--freshness", "24h"])

    mock_batch.assert_called_once_with([])
    assert result.exit_code == 0


def test_scan_freshness_passes_fresh_offer_to_scoring():
    """--freshness laisse passer les offres récentes vers score_batch."""
    from offerlens.pipeline.scoring import JobScore, ScoredOffer

    fresh = _offer(_now() - timedelta(hours=2), title="Fresh Offer")
    scored = ScoredOffer(
        offer=fresh,
        job_score=JobScore(score=3, explanation="ok", matched_skills=[], missing_skills=[], red_flags=[]),
    )

    mock_adapter = MagicMock()
    mock_adapter.search.return_value = [fresh]

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[mock_adapter]),
        patch("offerlens.pipeline.scoring.OfferScorer.score_batch", return_value=[scored]) as mock_batch,
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=False),
        patch("offerlens.pipeline.scan.save_scored_offer", return_value="id1"),
    ):
        result = runner.invoke(app, ["scan", "--freshness", "24h"])

    mock_batch.assert_called_once_with([fresh])
    assert result.exit_code == 0
