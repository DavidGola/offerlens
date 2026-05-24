"""Gmail API — OAuth2 user-scoped + envoi du digest HTML top 5."""

import base64
import traceback
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from offerlens.config import settings
from offerlens.notify.template import build_digest_html as _build_html
from offerlens.pipeline.scoring import ScoredOffer

_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
_CREDENTIALS_FILE = Path("credentials.json")
_TOKEN_FILE = Path(settings.gmail_oauth_token_path or "token.json")


def _get_gmail_service():
    if settings.gmail_refresh_token and settings.gmail_client_id and settings.gmail_client_secret:
        creds = Credentials(
            token=None,
            refresh_token=settings.gmail_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            scopes=_SCOPES,
        )
        creds.refresh(Request())
        return build("gmail", "v1", credentials=creds)

    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_FILE), _SCOPES
            )
            creds = flow.run_local_server(port=0)
            _TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def send_digest(
    top_offers: list[ScoredOffer],
    recipient: str | None = None,
    total_today: int = 0,
    warnings: list[str] | None = None,
) -> None:
    recipient = recipient or settings.gmail_recipient
    scan_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    html = _build_html(top_offers, scan_date, total_today=total_today, warnings=warnings)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"offerlens — {len(top_offers)} offres sur {total_today} scorées du {scan_date}"
    )
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    service = _get_gmail_service()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def send_error_email(error: Exception, recipient: str | None = None) -> None:
    recipient = recipient or settings.gmail_recipient
    date = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    tb = (
        traceback.format_exc()
        if traceback.format_exc().strip() != "NoneType: None"
        else traceback.format_exception(type(error), error, error.__traceback__)
    )
    body = "".join(tb) if isinstance(tb, list) else tb

    msg = MIMEText(body, "plain")
    msg["Subject"] = f"[offerlens] ERREUR pipeline — {date}"
    msg["To"] = recipient

    service = _get_gmail_service()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
