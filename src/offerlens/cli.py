"""CLI Typer — point d'entrée offerlens."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="offerlens", help="Lentille intelligente sur les offres d'emploi."
)
console = Console()


@app.command()
def ingest_cv(path: Annotated[Path, typer.Argument(help="Chemin vers le CV en PDF")]):
    """Ingère le CV PDF dans Firestore (opération one-shot)."""
    from offerlens.pipeline.ingestion import ingest_cv as _ingest

    with console.status("Ingestion du CV en cours..."):
        n = _ingest(path)
    console.print(f"[green]✓[/green] {n} chunks ingérés dans Firestore.")


def _run_scan(
    source: Optional[str] = None,
    query: str = "python backend",
    limit: int = 20,
    freshness: Optional[str] = None,
) -> list[str]:
    """Scanne toutes les sources configurées et retourne les warnings."""
    from offerlens.pipeline.scoring import score_offer
    from offerlens.sources.base import dedup_offers, filter_by_freshness
    from offerlens.sources.registry import get_sources
    from offerlens.storage.firestore import purge_old_offers

    purge_old_offers()

    adapters = get_sources(source_filter=source)
    all_offers = []
    warnings: list[str] = []

    for adapter in adapters:
        name = adapter.__class__.__name__.replace("Adapter", "").lower()
        try:
            with console.status(f"Recherche {name} : '{query}' (limit={limit})..."):
                offers = adapter.search(query, limit=limit)
            all_offers.extend(offers)
        except Exception as e:
            console.print(f"[yellow]⚠ {name} indisponible : {e}[/yellow]")
            warnings.append(f"{name} indisponible lors du scan ({type(e).__name__})")

    all_offers = dedup_offers(all_offers)

    if freshness:
        try:
            all_offers = filter_by_freshness(all_offers, freshness)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        console.print(
            f"[dim]{len(all_offers)} offre(s) après filtre fraîcheur ({freshness}).[/dim]"
        )

    table = Table(title=f"Top offres — {source or 'toutes sources'}", show_lines=True)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Titre", min_width=30)
    table.add_column("Entreprise", min_width=20)
    table.add_column("Source", width=14)
    table.add_column("Matched skills", min_width=30)

    results = []
    for offer in all_offers:
        with console.status(f"Scoring : {offer.title[:50]}..."):
            result = score_offer(offer)
        if result is not None:
            results.append(result)

    results.sort(key=lambda r: r.job_score.score, reverse=True)

    for result in results[:5]:
        score = result.job_score.score
        color = "green" if score >= 4 else "yellow" if score >= 2 else "red"
        table.add_row(
            f"[{color}]{score}/5[/{color}]",
            result.offer.title,
            result.offer.company,
            result.offer.source,
            ", ".join(result.job_score.matched_skills[:3]),
        )

    console.print(table)
    console.print(
        f"\n[dim]{len(results)} offres scorées, {len(results)} sauvegardées dans Firestore.[/dim]"
    )
    return warnings


def _run_digest(warnings: Optional[list[str]] = None) -> None:
    from offerlens.notify.gmail import send_digest
    from offerlens.pipeline.scoring import JobScore, ScoredOffer
    from offerlens.sources.base import RawOffer
    from offerlens.storage.firestore import count_today_offers, get_top_offers

    with console.status("Récupération des meilleures offres..."):
        raw_offers = get_top_offers(limit=5)
        total_today = count_today_offers()

    if not raw_offers:
        console.print("[yellow]Aucune offre nouvelle à envoyer.[/yellow]")
        return

    scored = []
    for o in raw_offers:
        offer = RawOffer(
            source=o.get("source", ""),
            url=o.get("url", ""),
            title=o.get("title", ""),
            company=o.get("company", ""),
            raw_content=o.get("raw_content", ""),
            location=o.get("location", ""),
            posted_at=o.get("posted_at"),
        )
        job_score = JobScore(
            score=o.get("score", 0),
            explanation=o.get("explanation", ""),
            matched_skills=o.get("matched_skills", []),
            missing_skills=o.get("missing_skills", []),
            red_flags=o.get("red_flags", []),
        )
        scored.append(ScoredOffer(offer=offer, job_score=job_score, offer_id=o["id"]))

    with console.status("Envoi du digest Gmail..."):
        send_digest(scored, total_today=total_today, warnings=warnings or [])

    console.print(
        f"[green]✓[/green] Digest envoyé — {len(scored)} offres sur {total_today} scorées."
    )


@app.command()
def scan(
    source: Annotated[
        Optional[str], typer.Option(help="Source unique : remotive, adzuna, francetravail")
    ] = None,
    query: Annotated[str, typer.Option(help="Requête de recherche")] = "python backend",
    limit: Annotated[int, typer.Option(help="Nombre max d'offres à scorer par source")] = 20,
    freshness: Annotated[
        Optional[str], typer.Option(help="Fenêtre de fraîcheur : 24h, 7d, 30d")
    ] = None,
):
    """Scanne et score des offres d'emploi (toutes les sources par défaut)."""
    _run_scan(source=source, query=query, limit=limit, freshness=freshness)


@app.command()
def digest():
    """Génère et envoie le digest email top 5 du jour."""
    _run_digest()


@app.command()
def run_pipeline(
    source: Annotated[
        Optional[str], typer.Option(help="Source unique : remotive, adzuna, francetravail")
    ] = None,
    query: Annotated[str, typer.Option(help="Requête de recherche")] = "python backend",
    limit: Annotated[int, typer.Option(help="Nombre max d'offres à scorer par source")] = 20,
    freshness: Annotated[
        Optional[str], typer.Option(help="Fenêtre de fraîcheur : 24h, 7d, 30d")
    ] = None,
):
    """Exécute le pipeline complet : scan → digest. Envoie un mail d'erreur en cas d'échec."""
    from offerlens.notify.gmail import send_error_email

    warnings: list[str] = []
    try:
        warnings = _run_scan(source=source, query=query, limit=limit, freshness=freshness)
    except Exception as e:
        send_error_email(e)
        raise

    try:
        _run_digest(warnings=warnings)
    except Exception as e:
        send_error_email(e)
        raise


@app.command()
def eval(
    dataset: Annotated[str, typer.Option(help="Nom du dataset LangSmith")] = "golden",
):
    """Lance l'évaluation sur le golden set LangSmith."""
    console.print("[yellow]Eval — non implémenté (étape 10).[/yellow]")


def main():
    app()


if __name__ == "__main__":
    main()
