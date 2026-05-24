"""Tests dédoublonnage cross-source par hash normalize(title+company)."""

from offerlens.sources.base import RawOffer, dedup_offers


def _offer(title: str, company: str, source: str = "remotive") -> RawOffer:
    return RawOffer(source=source, url=f"https://example.com/{title}", title=title, company=company, raw_content="")


def test_unique_offers_all_kept():
    offers = [_offer("Python Dev", "Acme"), _offer("Data Engineer", "Beta")]
    assert len(dedup_offers(offers)) == 2


def test_same_title_and_company_different_sources_deduped():
    o1 = _offer("Python Dev", "Acme", source="remotive")
    o2 = _offer("Python Dev", "Acme", source="adzuna")
    result = dedup_offers([o1, o2])
    assert len(result) == 1
    assert result[0].source == "remotive"  # first wins


def test_same_company_different_title_both_kept():
    o1 = _offer("Python Dev", "Acme")
    o2 = _offer("Data Engineer", "Acme")
    assert len(dedup_offers([o1, o2])) == 2


def test_normalization_case_insensitive():
    o1 = _offer("Python Dev", "Acme Corp")
    o2 = _offer("PYTHON DEV", "ACME CORP")
    assert len(dedup_offers([o1, o2])) == 1


def test_normalization_strips_whitespace():
    o1 = _offer("Python Dev", "Acme")
    o2 = _offer("  Python Dev  ", "  Acme  ")
    assert len(dedup_offers([o1, o2])) == 1


def test_first_occurrence_wins():
    o1 = _offer("Python Dev", "Acme", source="adzuna")
    o2 = _offer("Python Dev", "Acme", source="francetravail")
    result = dedup_offers([o1, o2])
    assert result[0].source == "adzuna"
