"""Template HTML pour le digest email offerlens."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from offerlens.pipeline.scoring import ScoredOffer

_SCORE_COLORS = {"high": "#22c55e", "mid": "#eab308", "low": "#ef4444"}


def _score_color(score: int) -> str:
    if score >= 4:
        return _SCORE_COLORS["high"]
    if score >= 2:
        return _SCORE_COLORS["mid"]
    return _SCORE_COLORS["low"]


def build_digest_html(
    offers: list[ScoredOffer],
    scan_date: str,
    total_today: int = 0,
    warnings: list[str] | None = None,
) -> str:
    rows = ""
    for r in offers:
        skills = ", ".join(r.job_score.matched_skills[:4]) or "—"
        posted = r.offer.posted_at.strftime("%d/%m/%Y") if r.offer.posted_at else "N/A"
        rows += f"""
        <tr>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;">
            <strong><a href="{r.offer.url}" style="color:#1d4ed8;">{r.offer.title}</a></strong><br>
            <span style="color:#6b7280;">{r.offer.company} · {r.offer.location}</span>
          </td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:center;">
            <span style="font-size:1.5em;font-weight:bold;color:{_score_color(r.job_score.score)};">{r.job_score.score}/5</span>
          </td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;text-align:center;color:#6b7280;">
            {posted}
          </td>
          <td style="padding:12px;border-bottom:1px solid #e5e7eb;">
            <p style="margin:0 0 6px;">{r.job_score.explanation}</p>
            <small style="color:#6b7280;">✅ {skills}</small>
          </td>
        </tr>"""

    warning_banner = ""
    if warnings:
        items = "".join(f"<li>{w}</li>" for w in warnings)
        warning_banner = f"""
  <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:12px 16px;margin-bottom:16px;">
    <strong style="color:#92400e;">⚠ Sources indisponibles lors de ce scan :</strong>
    <ul style="margin:6px 0 0;color:#78350f;">{items}</ul>
  </div>"""

    total_line = f"{total_today} offres scorées aujourd'hui." if total_today else ""
    return f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:800px;margin:0 auto;padding:20px;">
  <h1 style="color:#1e293b;">\U0001f50d offerlens — {scan_date}</h1>
  {warning_banner}
  <p style="color:#6b7280;">Top {len(offers)} offres (sur {total_today} scorées ce jour).</p>
  <table style="width:100%;border-collapse:collapse;">
    <thead>
      <tr style="background:#f8fafc;">
        <th style="padding:12px;text-align:left;">Offre</th>
        <th style="padding:12px;">Score</th>
        <th style="padding:12px;">Publiée le</th>
        <th style="padding:12px;text-align:left;">Analyse</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#9ca3af;font-size:0.8em;margin-top:24px;">offerlens · {scan_date} · {total_line}</p>
</body></html>"""
