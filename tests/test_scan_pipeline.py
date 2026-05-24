"""Tests unitaires ScanPipeline — flow fetch → dedup → filter → score → persist."""

from unittest.mock import MagicMock, patch

from offerlens.pipeline.scan import ScanPipeline, ScanResult
from offerlens.pipeline.scoring import JobScore, OfferScorer, ScoredOffer
from offerlens.sources.base import RawOffer


def _offer(title: str = "Python Dev", source: str = "test", url: str = "") -> RawOffer:
    return RawOffer(
        source=source, url=url or f"https://x.com/{title}",
        title=title, company="ACME",
        raw_content="Python backend", location="remote",
    )


def _scored(offer: RawOffer, score: int = 4) -> ScoredOffer:
    return ScoredOffer(
        offer=offer,
        job_score=JobScore(score=score, explanation="ok", matched_skills=["Python"], missing_skills=[], red_flags=[]),
    )


def _mock_scorer(offers_to_scored=None):
    """Crée un scorer mock qui retourne des ScoredOffer pour chaque offre."""
    scorer = MagicMock(spec=OfferScorer)
    if offers_to_scored:
        scorer.score_batch.side_effect = offers_to_scored
    else:
        scorer.score_batch.side_effect = lambda offers: [_scored(o) for o in offers]
    return scorer


# ── Flow basique ─────────────────────────────────────────────────────────────


def test_pipeline_returns_scan_result():
    adapter = MagicMock(search=MagicMock(return_value=[_offer()]))

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[adapter]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=False),
        patch("offerlens.pipeline.scan.save_scored_offer", return_value="id1"),
    ):
        result = ScanPipeline(_mock_scorer()).run()

    assert isinstance(result, ScanResult)
    assert len(result.scored) == 1
    assert result.scored[0].job_score.score == 4


def test_pipeline_passes_query_and_limit_to_adapters():
    adapter = MagicMock(search=MagicMock(return_value=[]))

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[adapter]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
    ):
        ScanPipeline(_mock_scorer()).run(query="data engineer", limit=10)

    adapter.search.assert_called_once_with("data engineer", limit=10)


# ── Dedup ────────────────────────────────────────────────────────────────────


def test_pipeline_deduplicates_offers_from_same_source():
    """Deux offres identiques (même titre+company) → une seule scorée."""
    o1 = _offer("Python Dev", source="remotive", url="https://a.com/1")
    o2 = _offer("Python Dev", source="adzuna", url="https://b.com/2")
    adapter = MagicMock(search=MagicMock(return_value=[o1, o2]))

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[adapter]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=False),
        patch("offerlens.pipeline.scan.save_scored_offer", return_value="id1"),
    ):
        result = ScanPipeline(_mock_scorer()).run()

    assert len(result.scored) == 1


# ── Contract type filter ─────────────────────────────────────────────────────


def test_pipeline_filters_stage_offers():
    """Les offres de stage/alternance sont exclues avant le scoring."""
    stage = _offer("Stage Python", url="https://x.com/stage")
    real = _offer("Senior Python Dev", url="https://x.com/senior")
    adapter = MagicMock(search=MagicMock(return_value=[stage, real]))
    scorer = _mock_scorer()

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[adapter]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=False),
        patch("offerlens.pipeline.scan.save_scored_offer", return_value="id1"),
    ):
        result = ScanPipeline(scorer).run()

    scored_titles = [s.offer.title for s in result.scored]
    assert "Stage Python" not in scored_titles
    assert "Senior Python Dev" in scored_titles


# ── offer_exists filter ──────────────────────────────────────────────────────


def test_pipeline_skips_already_scored_offers():
    """Les offres déjà en base ne sont pas re-scorées."""
    offer = _offer("Already Scored")
    adapter = MagicMock(search=MagicMock(return_value=[offer]))
    scorer = _mock_scorer()

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[adapter]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=True),
    ):
        result = ScanPipeline(scorer).run()

    assert result.scored == []
    scorer.score_batch.assert_called_once_with([])


# ── Source error handling ────────────────────────────────────────────────────


def test_pipeline_continues_when_one_source_fails():
    """Si un adapter échoue, les autres sont quand même scorés."""
    good_offer = _offer("Good Offer")
    good_adapter = MagicMock(search=MagicMock(return_value=[good_offer]))
    bad_adapter = MagicMock(search=MagicMock(side_effect=ConnectionError("timeout")))
    bad_adapter.__class__.__name__ = "BrokenAdapter"

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[bad_adapter, good_adapter]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=False),
        patch("offerlens.pipeline.scan.save_scored_offer", return_value="id1"),
    ):
        result = ScanPipeline(_mock_scorer()).run()

    assert len(result.scored) == 1
    assert len(result.warnings) == 1
    assert "indisponible" in result.warnings[0]


# ── Persist ──────────────────────────────────────────────────────────────────


def test_pipeline_persists_scored_offers():
    """Chaque offre scorée est sauvegardée via save_scored_offer."""
    offers = [_offer("A", url="https://a.com"), _offer("B", url="https://b.com")]
    adapter = MagicMock(search=MagicMock(return_value=offers))

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[adapter]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
        patch("offerlens.pipeline.scan.offer_exists", return_value=False),
        patch("offerlens.pipeline.scan.save_scored_offer", return_value="id1") as mock_save,
    ):
        result = ScanPipeline(_mock_scorer()).run()

    assert mock_save.call_count == 2
    assert all(r.offer_id == "id1" for r in result.scored)


# ── Source names ─────────────────────────────────────────────────────────────


def test_pipeline_reports_source_names():
    class RemotiveAdapter:
        def search(self, query, limit=50):
            return []

    with (
        patch("offerlens.pipeline.scan.get_sources", return_value=[RemotiveAdapter()]),
        patch("offerlens.pipeline.scan.purge_old_offers"),
    ):
        result = ScanPipeline(_mock_scorer()).run()

    assert result.source_names == ["remotive"]
