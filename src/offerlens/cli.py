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
    from offerlens.pipeline.scan import ScanPipeline
    from offerlens.pipeline.scoring import OfferScorer

    scorer = OfferScorer()
    pipeline = ScanPipeline(scorer)

    with console.status("Scan en cours..."):
        result = pipeline.run(
            query=query, limit=limit, source_filter=source, freshness=freshness
        )

    console.print(f"[dim]Sources actives : {', '.join(result.source_names)}[/dim]")
    for w in result.warnings:
        console.print(f"[yellow]⚠ {w}[/yellow]")

    table = Table(title=f"Top offres — {source or 'toutes sources'}", show_lines=True)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Titre", min_width=30)
    table.add_column("Entreprise", min_width=20)
    table.add_column("Source", width=14)
    table.add_column("Matched skills", min_width=30)

    for r in sorted(result.scored, key=lambda x: x.job_score.score, reverse=True)[:10]:
        score = r.job_score.score
        color = "green" if score >= 4 else "yellow" if score >= 2 else "red"
        table.add_row(
            f"[{color}]{score}/5[/{color}]",
            r.offer.title,
            r.offer.company,
            r.offer.source,
            ", ".join(r.job_score.matched_skills[:3]),
        )

    console.print(table)
    console.print(
        f"\n[dim]{len(result.scored)} offres scorées et sauvegardées dans Firestore.[/dim]"
    )
    return result.warnings


def _run_digest(warnings: Optional[list[str]] = None) -> None:
    from offerlens.notify.gmail import send_digest
    from offerlens.sources.base import filter_contract_type
    from offerlens.storage.firestore import count_today_offers, get_top_offers

    with console.status("Récupération des meilleures offres..."):
        scored = get_top_offers(limit=20)
        total_today = count_today_offers()

    if not scored:
        console.print("[yellow]Aucune offre nouvelle à envoyer.[/yellow]")
        return

    kept_urls = {o.url for o in filter_contract_type([s.offer for s in scored])}
    scored = [s for s in scored if s.offer.url in kept_urls][:10]

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
