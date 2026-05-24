"""Pipeline de scan — fetch → dedup → filter → score → persist."""

from __future__ import annotations

from dataclasses import dataclass, field

from offerlens.pipeline.scoring import OfferScorer, ScoredOffer
from offerlens.sources.base import RawOffer, dedup_offers, filter_by_freshness, filter_contract_type
from offerlens.sources.registry import get_sources
from offerlens.storage.firestore import offer_exists, purge_old_offers, save_scored_offer


@dataclass
class ScanResult:
    scored: list[ScoredOffer] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)


class ScanPipeline:
    """Orchestre fetch → dedup → filter → score → persist."""

    def __init__(self, scorer: OfferScorer):
        self._scorer = scorer

    def run(
        self,
        query: str = "python backend",
        limit: int = 20,
        source_filter: str | None = None,
        freshness: str | None = None,
    ) -> ScanResult:
        purge_old_offers()

        adapters = get_sources(source_filter=source_filter)
        source_names = [a.__class__.__name__.replace("Adapter", "").lower() for a in adapters]
        warnings: list[str] = []
        all_offers: list[RawOffer] = []

        for adapter in adapters:
            name = adapter.__class__.__name__.replace("Adapter", "").lower()
            try:
                all_offers.extend(adapter.search(query, limit=limit))
            except Exception as e:
                warnings.append(f"{name} indisponible lors du scan ({type(e).__name__}: {e})")

        all_offers = dedup_offers(all_offers)
        all_offers = filter_contract_type(all_offers)

        if freshness:
            all_offers = filter_by_freshness(all_offers, freshness)

        all_offers = [o for o in all_offers if not offer_exists(o.source, o.url)]

        scored = self._scorer.score_batch(all_offers)

        for s in scored:
            s.offer_id = save_scored_offer(s)

        return ScanResult(scored=scored, warnings=warnings, source_names=source_names)
