"""Tests de la commande run-pipeline et send_error_email."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from offerlens.cli import app

runner = CliRunner()


# ── send_error_email ──────────────────────────────────────────────────────────


def test_send_error_email_exists():
    from offerlens.notify.gmail import send_error_email

    assert callable(send_error_email)


def test_send_error_email_subject_format():
    """Le sujet contient '[offerlens] ERREUR pipeline — ' et la date."""
    import base64
    from email import message_from_bytes
    from email.header import decode_header
    from offerlens.notify.gmail import send_error_email

    captured = {}

    def fake_send(userId, body):
        raw = base64.urlsafe_b64decode(body["raw"] + "==")
        msg = message_from_bytes(raw)
        parts = decode_header(msg["Subject"])
        subject = "".join(
            part.decode(enc or "utf-8") if isinstance(part, bytes) else part
            for part, enc in parts
        )
        captured["subject"] = subject
        m = MagicMock()
        m.execute.return_value = {}
        return m

    with patch("offerlens.notify.gmail._get_gmail_service") as mock_svc:
        mock_svc.return_value.users.return_value.messages.return_value.send.side_effect = fake_send
        send_error_email(ValueError("boom"))

    assert "[offerlens] ERREUR pipeline" in captured["subject"]
    assert "—" in captured["subject"]


def test_send_error_email_body_contains_traceback():
    """Le body contient le traceback brut."""
    import base64
    from email import message_from_bytes
    from offerlens.notify.gmail import send_error_email

    captured = {}

    def fake_send(userId, body):
        raw = base64.urlsafe_b64decode(body["raw"] + "==")
        msg = message_from_bytes(raw)
        captured["content_type"] = msg.get_content_type()
        captured["body"] = msg.get_payload(decode=True).decode() if msg.get_payload(decode=True) else msg.get_payload()
        m = MagicMock()
        m.execute.return_value = {}
        return m

    try:
        raise RuntimeError("test error details")
    except RuntimeError as e:
        err = e

    with patch("offerlens.notify.gmail._get_gmail_service") as mock_svc:
        mock_svc.return_value.users.return_value.messages.return_value.send.side_effect = fake_send
        send_error_email(err)

    assert "RuntimeError" in captured["body"]
    assert "test error details" in captured["body"]


def test_send_error_email_is_plain_text():
    """Le mail d'erreur est en texte plain (pas HTML)."""
    import base64
    from email import message_from_bytes
    from offerlens.notify.gmail import send_error_email

    captured = {}

    def fake_send(userId, body):
        raw = base64.urlsafe_b64decode(body["raw"] + "==")
        msg = message_from_bytes(raw)
        captured["content_type"] = msg.get_content_type()
        m = MagicMock()
        m.execute.return_value = {}
        return m

    with patch("offerlens.notify.gmail._get_gmail_service") as mock_svc:
        mock_svc.return_value.users.return_value.messages.return_value.send.side_effect = fake_send
        send_error_email(ValueError("x"))

    assert captured["content_type"] == "text/plain"


# ── run-pipeline CLI ──────────────────────────────────────────────────────────


def test_run_pipeline_command_exists():
    """La commande run-pipeline est enregistrée dans l'app Typer."""
    result = runner.invoke(app, ["run-pipeline", "--help"])
    assert result.exit_code == 0


def test_run_pipeline_calls_scan_then_digest():
    """run-pipeline exécute scan puis digest en séquence."""
    call_order = []

    def fake_scan(*args, **kwargs):
        call_order.append("scan")
        return []

    def fake_digest(*args, **kwargs):
        call_order.append("digest")

    with (
        patch("offerlens.cli._run_scan", side_effect=fake_scan),
        patch("offerlens.cli._run_digest", side_effect=fake_digest),
    ):
        result = runner.invoke(app, ["run-pipeline"])

    assert result.exit_code == 0
    assert call_order == ["scan", "digest"]


def test_run_pipeline_accepts_scan_options():
    """run-pipeline accepte --query, --limit, --freshness, --source."""
    with (
        patch("offerlens.cli._run_scan") as mock_scan,
        patch("offerlens.cli._run_digest"),
    ):
        result = runner.invoke(
            app,
            ["run-pipeline", "--query", "python", "--limit", "10", "--freshness", "7d", "--source", "remotive"],
        )

    assert result.exit_code == 0
    mock_scan.assert_called_once_with(
        source="remotive",
        query="python",
        limit=10,
        freshness="7d",
    )


def test_run_pipeline_sends_error_email_on_scan_failure():
    """En cas d'erreur sur scan, un mail d'erreur est envoyé."""
    with (
        patch("offerlens.cli._run_scan", side_effect=RuntimeError("scan boom")),
        patch("offerlens.cli._run_digest"),
        patch("offerlens.notify.gmail.send_error_email") as mock_err,
    ):
        result = runner.invoke(app, ["run-pipeline"])

    mock_err.assert_called_once()
    err_arg = mock_err.call_args.args[0]
    assert isinstance(err_arg, RuntimeError)


def test_run_pipeline_reraises_after_error_email():
    """Après envoi du mail d'erreur, l'exception est re-raised (exit code non-zero)."""
    with (
        patch("offerlens.cli._run_scan", side_effect=RuntimeError("scan boom")),
        patch("offerlens.cli._run_digest"),
        patch("offerlens.notify.gmail.send_error_email"),
    ):
        result = runner.invoke(app, ["run-pipeline"])

    assert result.exit_code != 0


def test_run_pipeline_sends_error_email_on_digest_failure():
    """En cas d'erreur sur digest, un mail d'erreur est envoyé."""
    with (
        patch("offerlens.cli._run_scan"),
        patch("offerlens.cli._run_digest", side_effect=RuntimeError("digest boom")),
        patch("offerlens.notify.gmail.send_error_email") as mock_err,
    ):
        result = runner.invoke(app, ["run-pipeline"])

    mock_err.assert_called_once()
    err_arg = mock_err.call_args.args[0]
    assert isinstance(err_arg, RuntimeError)


def test_run_pipeline_digest_not_called_after_scan_failure():
    """Si scan échoue, digest n'est pas exécuté."""
    call_order = []

    with (
        patch("offerlens.cli._run_scan", side_effect=RuntimeError("scan boom")),
        patch("offerlens.cli._run_digest", side_effect=lambda: call_order.append("digest")),
        patch("offerlens.notify.gmail.send_error_email"),
    ):
        runner.invoke(app, ["run-pipeline"])

    assert "digest" not in call_order
