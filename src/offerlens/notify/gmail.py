"""Gmail API — OAuth2 user-scoped + envoi du digest HTML top 5."""

import base64
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from offerlens.config import settings
from offerlens.pipeline.scoring import ScoredOffer

_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
_CREDENTIALS_FILE = Path("credentials.json")
_TOKEN_FILE = Path(settings.gmail_oauth_token_path or "token.json")


def _get_gmail_service():
    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Don't write back — token file may be read-only (Cloud Run secret mount).
            # refresh_token is stable; access token is refreshed in memory each run.
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS_FILE), _SCOPES)
            creds = flow.run_local_server(port=0)
            _TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _build_html(offers: list[ScoredOffer], scan_date: str) -> str:
    rows = ""
    for r in offers:
        score_color = "#22c55e" if r.job_score.score >= 4 else "#eab308" if r.job_score.score >= 2 else "#ef4444"
        skills = ", ".join(r.job_score.matched_skills[:4]) or "—"
        rows += f"""
        <tr>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;">
            <strong><a href="{r.offer.url}" style="color:#1d4ed8;">{r.offer.title}</a></strong><br>
            <span style="color:#6b7280;">{r.offer.company} · {r.offer.location}</span>
          </td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:center;">
            <span style="font-size:1.5em;font-weight:bold;color:{score_color};">{r.job_score.score}/5</span>
          </td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;">
            <p style="margin:0 0 6px;">{r.job_score.explanation}</p>
            <small style="color:#6b7280;">✅ {skills}</small>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:800px;margin:0 auto;padding:20px;">
  <h1 style="color:#1e293b;">🔍 offerlens — {scan_date}</h1>
  <p style="color:#6b7280;">Top {len(offers)} offres du jour, scorées contre ton CV.</p>
  <table style="width:100%;border-collapse:collapse;">
    <thead>
      <tr style="background:#f8fafc;">
        <th style="padding:12px;text-align:left;">Offre</th>
        <th style="padding:12px;">Score</th>
        <th style="padding:12px;text-align:left;">Analyse</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#9ca3af;font-size:0.8em;margin-top:24px;">offerlens · {scan_date}</p>
</body></html>"""


def send_digest(top_offers: list[ScoredOffer], recipient: str | None = None) -> None:
    recipient = recipient or settings.gmail_recipient
    scan_date = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    html = _build_html(top_offers, scan_date)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"offerlens — {len(top_offers)} offres du {scan_date}"
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    service = _get_gmail_service()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
