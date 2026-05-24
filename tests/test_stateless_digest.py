"""Tests du digest stateless — suppression de seen_at/status/mark_offers_seen."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from offerlens.cli import app
from offerlens.pipeline.scoring import JobScore, ScoredOffer
from offerlens.sources.base import RawOffer


def _make_scored(title: str = "Dev") -> ScoredOffer:
    offer = RawOffer(
        source="test", url="https://x.com", title=title,
        company="ACME", raw_content="Python", location="remote",
    )
    job_score = JobScore(score=5, explanation="ok", matched_skills=[], missing_skills=[], red_flags=[])
    return ScoredOffer(offer=offer, job_score=job_score, offer_id="abc")


# ── OfferScorer ne persiste pas ──────────────────────────────────────────────

def test_scorer_does_not_persist():
    """OfferScorer.score() retourne un ScoredOffer sans toucher Firestore."""
    from langchain_core.runnables import RunnableLambda

    from offerlens.pipeline.scoring import OfferScorer

    offer = RawOffer(
        source="test", url="https://x.com", title="Dev",
        company="ACME", raw_content="Python", location="remote",
    )
    job_score = JobScore(score=4, explanation="ok", matched_skills=[], missing_skills=[], red_flags=[])

    fake_llm = RunnableLambda(lambda _: job_score)
    scorer = OfferScorer(
        llm=MagicMock(with_structured_output=MagicMock(return_value=fake_llm)),
        cv_retriever=lambda _: "chunk",
    )

    result = scorer.score(offer)

    assert result.job_score.score == 4
    assert result.offer_id == ""


# ── mark_offers_seen n'existe plus ───────────────────────────────────────────

def test_mark_offers_seen_does_not_exist():
    """mark_offers_seen doit être supprimé du module firestore."""
    import offerlens.storage.firestore as fs
    assert not hasattr(fs, "mark_offers_seen")


# ── get_top_offers ne filtre plus par seen_at ni status ──────────────────────

def test_get_top_offers_no_status_filter():
    """get_top_offers ne doit pas filtrer sur status ou seen_at."""
    mock_doc = MagicMock()
    mock_doc.id = "abc"
    mock_doc.to_dict.return_value = {
        "source": "test", "url": "https://x.com", "title": "Dev",
        "company": "ACME", "raw_content": "Python", "location": "remote",
        "score": 5, "explanation": "ok",
        "matched_skills": [], "missing_skills": [], "red_flags": [],
    }

    mock_query = MagicMock()
    mock_query.order_by.return_value.limit.return_value.get.return_value = [mock_doc]

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value = mock_query
        from offerlens.storage.firestore import get_top_offers
        results = get_top_offers(limit=1)

    mock_query.where.assert_not_called()
    assert len(results) == 1
    assert results[0].job_score.score == 5


# ── digest n'appelle plus mark_offers_seen ────────────────────────────────────

runner = CliRunner()


def test_digest_does_not_call_mark_offers_seen():
    """La commande digest ne doit plus appeler mark_offers_seen."""
    with (
        patch("offerlens.storage.firestore.get_top_offers", return_value=[_make_scored()]),
        patch("offerlens.storage.firestore.count_today_offers", return_value=1),
        patch("offerlens.notify.gmail.send_digest"),
        patch("offerlens.cli.mark_offers_seen", create=True) as mock_seen,
    ):
        result = runner.invoke(app, ["digest"])

    mock_seen.assert_not_called()
    assert result.exit_code == 0


def test_digest_twice_returns_same_offers():
    """Exécuter digest deux fois de suite retourne les mêmes offres (stateless)."""
    with (
        patch("offerlens.storage.firestore.get_top_offers", return_value=[_make_scored()]) as mock_get,
        patch("offerlens.storage.firestore.count_today_offers", return_value=1),
        patch("offerlens.notify.gmail.send_digest"),
    ):
        runner.invoke(app, ["digest"])
        runner.invoke(app, ["digest"])
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0] == mock_get.call_args_list[1]
