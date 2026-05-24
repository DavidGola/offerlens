"""CLI Typer — point d'entrée offerlens."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="offerlens", help="Lentille intelligente sur les offres d'emploi.")
console = Console()


@app.command()
def ingest_cv(path: Annotated[Path, typer.Argument(help="Chemin vers le CV en PDF")]):
    """Ingère le CV PDF dans Firestore (opération one-shot)."""
    from offerlens.pipeline.ingestion import ingest_cv as _ingest

    with console.status("Ingestion du CV en cours..."):
        n = _ingest(path)
    console.print(f"[green]✓[/green] {n} chunks ingérés dans Firestore.")


@app.command()
def scan(
    source: Annotated[str, typer.Option(help="Source : remotive")] = "remotive",
    query: Annotated[str, typer.Option(help="Requête de recherche")] = "python backend",
    limit: Annotated[int, typer.Option(help="Nombre max d'offres à scorer")] = 20,
    url: Annotated[Optional[str], typer.Option(help="URL unique à scorer (mode paste)")] = None,
    freshness: Annotated[Optional[str], typer.Option(help="Fenêtre de fraîcheur : 24h, 7d, 30d")] = None,
):
    """Scanne et score des offres d'emploi."""
    from offerlens.pipeline.scoring import score_offer
    from offerlens.sources.base import filter_by_freshness
    from offerlens.sources.remotive import RemotiveAdapter
    from offerlens.sources.url_fetch import URLFetchAdapter

    if url:
        with console.status(f"Récupération de l'offre depuis {url}..."):
            offer = URLFetchAdapter().fetch_by_url(url)
        offers = [offer]
    elif source == "remotive":
        with console.status(f"Recherche Remotive : '{query}' (limit={limit})..."):
            offers = RemotiveAdapter().search(query, limit=limit)
    else:
        console.print(f"[red]Source inconnue : {source}[/red]")
        raise typer.Exit(1)

    if freshness:
        try:
            offers = filter_by_freshness(offers, freshness)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        console.print(f"[dim]{len(offers)} offre(s) après filtre fraîcheur ({freshness}).[/dim]")

    table = Table(title=f"Top offres — {source}", show_lines=True)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Titre", min_width=30)
    table.add_column("Entreprise", min_width=20)
    table.add_column("Matched skills", min_width=30)

    results = []
    for offer in offers:
        with console.status(f"Scoring : {offer.title[:50]}..."):
            result = score_offer(offer)
        results.append(result)

    results.sort(key=lambda r: r.job_score.score, reverse=True)

    for result in results[:5]:
        score = result.job_score.score
        color = "green" if score >= 4 else "yellow" if score >= 2 else "red"
        table.add_row(
            f"[{color}]{score}/5[/{color}]",
            result.offer.title,
            result.offer.company,
            ", ".join(result.job_score.matched_skills[:3]),
        )

    console.print(table)
    console.print(f"\n[dim]{len(results)} offres scorées, {len(results)} sauvegardées dans Firestore.[/dim]")


@app.command()
def digest():
    """Génère et envoie le digest email top 5 du jour."""
    from offerlens.notify.gmail import send_digest
    from offerlens.pipeline.scoring import JobScore, ScoredOffer
    from offerlens.sources.base import RawOffer
    from offerlens.storage.firestore import get_top_offers

    with console.status("Récupération des meilleures offres..."):
        raw_offers = get_top_offers(limit=5)

    if not raw_offers:
        console.print("[yellow]Aucune offre nouvelle à envoyer.[/yellow]")
        raise typer.Exit(0)

    scored = []
    for o in raw_offers:
        offer = RawOffer(
            source=o.get("source", ""),
            url=o.get("url", ""),
            title=o.get("title", ""),
            company=o.get("company", ""),
            raw_content=o.get("raw_content", ""),
            location=o.get("location", ""),
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
        send_digest(scored)

    console.print(f"[green]✓[/green] Digest envoyé — {len(scored)} offres.")


@app.command()
def eval(dataset: Annotated[str, typer.Option(help="Nom du dataset LangSmith")] = "golden"):
    """Lance l'évaluation sur le golden set LangSmith."""
    console.print("[yellow]Eval — non implémenté (étape 10).[/yellow]")


def main():
    app()


if __name__ == "__main__":
    main()
