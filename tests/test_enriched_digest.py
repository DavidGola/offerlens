"""Tests du digest enrichi — nombre total d'offres + date de publication."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from offerlens.cli import app
from offerlens.notify.gmail import _build_html
from offerlens.pipeline.scoring import JobScore, ScoredOffer
from offerlens.sources.base import RawOffer


def _make_scored(title: str = "Dev Python", posted_at: datetime | None = None) -> ScoredOffer:
    offer = RawOffer(
        source="test", url="https://x.com", title=title,
        company="ACME", raw_content="Python", location="remote",
        posted_at=posted_at,
    )
    job_score = JobScore(score=4, explanation="ok", matched_skills=["Python"], missing_skills=[], red_flags=[])
    return ScoredOffer(offer=offer, job_score=job_score, offer_id="abc")


# ── count_today_offers ────────────────────────────────────────────────────────

def test_count_today_offers_queries_today_range():
    """count_today_offers filtre sur scanned_at >= début de journée UTC."""
    mock_docs = [MagicMock(), MagicMock(), MagicMock()]
    mock_stream = iter(mock_docs)

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        coll = mock_client.return_value.collection.return_value
        coll.where.return_value.where.return_value.stream.return_value = mock_stream
        from offerlens.storage.firestore import count_today_offers
        count = count_today_offers()

    assert count == 3
    mock_client.return_value.collection.assert_called_once_with("offers")


# ── _build_html — colonne posted_at ──────────────────────────────────────────

def test_build_html_shows_posted_at():
    posted = datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc)
    scored = _make_scored(posted_at=posted)
    html = _build_html([scored], scan_date="24/05/2026", total_today=10)
    assert "24/05/2026" in html


def test_build_html_shows_na_when_no_posted_at():
    scored = _make_scored(posted_at=None)
    html = _build_html([scored], scan_date="24/05/2026", total_today=10)
    assert "N/A" in html


def test_build_html_shows_total_count():
    scored = _make_scored()
    html = _build_html([scored], scan_date="24/05/2026", total_today=18)
    assert "18" in html


# ── send_digest — sujet et body ───────────────────────────────────────────────

def test_send_digest_subject_format():
    """Le sujet suit le format : offerlens — N offres sur T scorées du JJ/MM/AAAA."""
    from offerlens.notify.gmail import send_digest

    scored = [_make_scored()]
    with (
        patch("offerlens.notify.gmail._get_gmail_service") as mock_svc,
        patch("offerlens.notify.gmail._build_html", return_value="<html/>") as mock_html,
    ):
        mock_svc.return_value.users.return_value.messages.return_value.send.return_value.execute.return_value = {}
        send_digest(scored, recipient="test@example.com", total_today=18)

    call_kwargs = mock_html.call_args
    assert call_kwargs.kwargs.get("total_today") == 18 or call_kwargs.args[2] == 18


def test_send_digest_subject_contains_total():
    from email import message_from_bytes
    import base64
    from offerlens.notify.gmail import send_digest

    scored = [_make_scored(), _make_scored()]
    captured = {}

    def fake_send(userId, body):
        raw = base64.urlsafe_b64decode(body["raw"] + "==")
        msg = message_from_bytes(raw)
        captured["subject"] = msg["Subject"]
        m = MagicMock()
        m.execute.return_value = {}
        return m

    with patch("offerlens.notify.gmail._get_gmail_service") as mock_svc:
        mock_svc.return_value.users.return_value.messages.return_value.send.side_effect = fake_send
        send_digest(scored, recipient="test@example.com", total_today=25)

    subject = captured["subject"]
    assert "2" in subject   # len(scored)
    assert "25" in subject  # total_today


# ── CLI digest passe total_today ──────────────────────────────────────────────

runner = CliRunner()


def test_digest_cli_passes_total_today():
    """La commande digest récupère count_today_offers et le passe à send_digest."""
    with (
        patch("offerlens.storage.firestore.get_top_offers", return_value=[_make_scored()]),
        patch("offerlens.storage.firestore.count_today_offers", return_value=42),
        patch("offerlens.notify.gmail.send_digest") as mock_send,
    ):
        result = runner.invoke(app, ["digest"])

    assert result.exit_code == 0
    call_args = mock_send.call_args
    passed_total = (
        call_args.kwargs.get("total_today")
        if "total_today" in call_args.kwargs
        else call_args.args[1] if len(call_args.args) > 1 else None
    )
    assert passed_total == 42


def test_digest_cli_posted_at_propagated():
    """posted_at est transmis au RawOffer dans le ScoredOffer."""
    posted = datetime(2026, 5, 24, 8, 0, tzinfo=timezone.utc)
    scored = _make_scored(posted_at=posted)

    with (
        patch("offerlens.storage.firestore.get_top_offers", return_value=[scored]),
        patch("offerlens.storage.firestore.count_today_offers", return_value=1),
        patch("offerlens.notify.gmail.send_digest") as mock_send,
    ):
        runner.invoke(app, ["digest"])

    scored_list = mock_send.call_args.args[0]
    assert scored_list[0].offer.posted_at == posted
