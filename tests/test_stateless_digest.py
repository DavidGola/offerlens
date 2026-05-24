"""Tests du digest stateless — suppression de seen_at/status/mark_offers_seen."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from offerlens.cli import app


# ── score_offer ne persiste plus seen_at ni status ───────────────────────────

def test_score_offer_does_not_persist_seen_at():
    """save_scored_offer ne doit pas recevoir le champ seen_at."""
    from langchain_core.runnables import RunnableLambda

    from offerlens.pipeline.scoring import JobScore, score_offer
    from offerlens.sources.base import RawOffer

    offer = RawOffer(
        source="test", url="https://x.com", title="Dev",
        company="ACME", raw_content="Python", location="remote",
    )
    job_score = JobScore(score=4, explanation="ok", matched_skills=[], missing_skills=[], red_flags=[])

    with (
        patch("offerlens.pipeline.scoring.get_chat_model") as mock_llm,
        patch("offerlens.pipeline.scoring._retrieve_cv_chunks", return_value="chunk"),
        patch("offerlens.pipeline.scoring.save_scored_offer", return_value="id123") as mock_save,
    ):
        mock_llm.return_value.with_structured_output.return_value = RunnableLambda(lambda _: job_score)
        score_offer(offer)

    saved_data = mock_save.call_args[0][0]
    assert "seen_at" not in saved_data
    assert "status" not in saved_data


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
    mock_doc.to_dict.return_value = {"score": 5, "title": "Dev"}

    mock_query = MagicMock()
    mock_query.order_by.return_value.limit.return_value.get.return_value = [mock_doc]

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value = mock_query
        from offerlens.storage.firestore import get_top_offers
        results = get_top_offers(limit=1)

    mock_query.where.assert_not_called()
    assert results == [{"id": "abc", "score": 5, "title": "Dev"}]


# ── digest n'appelle plus mark_offers_seen ────────────────────────────────────

runner = CliRunner()


def test_digest_does_not_call_mark_offers_seen():
    """La commande digest ne doit plus appeler mark_offers_seen."""
    mock_offers = [
        {
            "id": "1", "source": "test", "url": "https://x.com",
            "title": "Dev", "company": "ACME", "raw_content": "Python",
            "location": "remote", "score": 5, "explanation": "ok",
            "matched_skills": [], "missing_skills": [], "red_flags": [],
        }
    ]
    with (
        patch("offerlens.storage.firestore.get_top_offers", return_value=mock_offers),
        patch("offerlens.notify.gmail.send_digest"),
        patch("offerlens.cli.mark_offers_seen", create=True) as mock_seen,
    ):
        result = runner.invoke(app, ["digest"])

    # mark_offers_seen ne doit pas être appelé (ne doit plus exister dans le CLI)
    mock_seen.assert_not_called()
    assert result.exit_code == 0


def test_digest_twice_returns_same_offers():
    """Exécuter digest deux fois de suite retourne les mêmes offres (stateless)."""
    mock_offers = [
        {
            "id": "1", "source": "test", "url": "https://x.com",
            "title": "Dev", "company": "ACME", "raw_content": "Python",
            "location": "remote", "score": 5, "explanation": "ok",
            "matched_skills": [], "missing_skills": [], "red_flags": [],
        }
    ]

    with (
        patch("offerlens.storage.firestore.get_top_offers", return_value=mock_offers) as mock_get,
        patch("offerlens.notify.gmail.send_digest"),
    ):
        runner.invoke(app, ["digest"])
        runner.invoke(app, ["digest"])
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0] == mock_get.call_args_list[1]
