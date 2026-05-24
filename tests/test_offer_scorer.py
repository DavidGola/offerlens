"""Tests unitaires OfferScorer — scoring via LLM injectable."""

from unittest.mock import MagicMock

from langchain_core.runnables import RunnableLambda

from offerlens.pipeline.scoring import JobScore, OfferScorer, ScoredOffer
from offerlens.sources.base import RawOffer


def _offer(title: str = "Python Backend Dev", company: str = "ACME") -> RawOffer:
    return RawOffer(
        source="test", url=f"https://x.com/{title}",
        title=title, company=company,
        raw_content="We need a Python dev with FastAPI experience.",
        location="Paris, remote",
    )


def _fake_score(score: int = 4) -> JobScore:
    return JobScore(
        score=score,
        explanation="Good match on Python and FastAPI.",
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Kubernetes"],
        red_flags=[],
    )


def _make_scorer(fake_job_score: JobScore | None = None) -> OfferScorer:
    job_score = fake_job_score or _fake_score()
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = RunnableLambda(lambda _: job_score)
    return OfferScorer(llm=fake_llm, cv_retriever=lambda _: "CV chunk: Python, FastAPI, Docker")


# ── score() ──────────────────────────────────────────────────────────────────


def test_score_returns_scored_offer():
    scorer = _make_scorer()
    result = scorer.score(_offer())

    assert isinstance(result, ScoredOffer)
    assert result.offer.title == "Python Backend Dev"
    assert result.job_score.score == 4


def test_score_does_not_set_offer_id():
    """Le scorer ne persiste pas — offer_id reste vide."""
    scorer = _make_scorer()
    result = scorer.score(_offer())

    assert result.offer_id == ""


def test_score_passes_offer_text_to_cv_retriever():
    retrieved_texts = []

    def tracking_retriever(offer_text: str) -> str:
        retrieved_texts.append(offer_text)
        return "chunk"

    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = RunnableLambda(lambda _: _fake_score())
    scorer = OfferScorer(llm=fake_llm, cv_retriever=tracking_retriever)

    scorer.score(_offer(title="Data Engineer", company="Beta"))

    assert len(retrieved_texts) == 1
    assert "Data Engineer" in retrieved_texts[0]
    assert "Beta" in retrieved_texts[0]


def test_score_propagates_all_job_score_fields():
    job_score = JobScore(
        score=2,
        explanation="Partial match.",
        matched_skills=["SQL"],
        missing_skills=["Go", "Rust"],
        red_flags=["Overqualified"],
    )
    scorer = _make_scorer(job_score)
    result = scorer.score(_offer())

    assert result.job_score.score == 2
    assert result.job_score.missing_skills == ["Go", "Rust"]
    assert result.job_score.red_flags == ["Overqualified"]


# ── score_batch() ────────────────────────────────────────────────────────────


def test_score_batch_empty_returns_empty():
    scorer = _make_scorer()
    assert scorer.score_batch([]) == []


def test_score_batch_scores_multiple_offers():
    scorer = _make_scorer()
    offers = [_offer("Dev A"), _offer("Dev B"), _offer("Dev C")]

    results = scorer.score_batch(offers)

    assert len(results) == 3
    assert results[0].offer.title == "Dev A"
    assert results[2].offer.title == "Dev C"
    assert all(r.job_score.score == 4 for r in results)


def test_score_batch_preserves_offer_order():
    """L'ordre des résultats correspond à l'ordre des offres en entrée."""
    scorer = _make_scorer()
    offers = [_offer(f"Offer {i}") for i in range(5)]

    results = scorer.score_batch(offers)

    for i, result in enumerate(results):
        assert result.offer.title == f"Offer {i}"


def test_score_batch_calls_cv_retriever_per_offer():
    call_count = []

    def counting_retriever(offer_text: str) -> str:
        call_count.append(1)
        return "chunk"

    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = RunnableLambda(lambda _: _fake_score())
    scorer = OfferScorer(llm=fake_llm, cv_retriever=counting_retriever)

    scorer.score_batch([_offer("A"), _offer("B"), _offer("C")])

    assert len(call_count) == 3
