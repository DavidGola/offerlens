"""Tests de dédoublonnage des offres par hash source + url."""

import hashlib
from unittest.mock import MagicMock, patch


# ── hash generation ───────────────────────────────────────────────────────────


def test_offer_id_is_sha256_of_source_and_url():
    """L'ID du document est sha256(source + url)[:16]."""
    source = "indeed"
    url = "https://indeed.com/viewjob?jk=abc123"
    expected = hashlib.sha256(f"{source}{url}".encode()).hexdigest()[:16]

    mock_doc_ref = MagicMock()
    mock_doc_ref.id = expected
    mock_doc_ref.get.return_value.exists = False

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value.document.return_value = mock_doc_ref
        from offerlens.storage.firestore import save_scored_offer

        offer_id = save_scored_offer(
            {"source": source, "url": url, "title": "Dev", "score": 4},
            source=source,
            url=url,
        )

    assert offer_id == expected
    mock_client.return_value.collection.return_value.document.assert_called_once_with(expected)


# ── skip on duplicate ─────────────────────────────────────────────────────────


def test_save_scored_offer_skips_existing_document():
    """Si le document existe déjà, save_scored_offer ne l'écrase pas et retourne l'ID existant."""
    source = "remotive"
    url = "https://remotive.com/job/12345"
    expected_id = hashlib.sha256(f"{source}{url}".encode()).hexdigest()[:16]

    mock_doc_ref = MagicMock()
    mock_doc_ref.id = expected_id
    mock_doc_ref.get.return_value.exists = True  # document already exists

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value.document.return_value = mock_doc_ref
        from offerlens.storage.firestore import save_scored_offer

        offer_id = save_scored_offer(
            {"source": source, "url": url, "title": "Dev", "score": 3},
            source=source,
            url=url,
        )

    # Must not overwrite
    mock_doc_ref.set.assert_not_called()
    assert offer_id == expected_id


def test_save_scored_offer_writes_new_document_when_not_exists():
    """Si le document n'existe pas encore, save_scored_offer l'écrit normalement."""
    source = "indeed"
    url = "https://indeed.com/viewjob?jk=new"
    expected_id = hashlib.sha256(f"{source}{url}".encode()).hexdigest()[:16]

    mock_doc_ref = MagicMock()
    mock_doc_ref.id = expected_id
    mock_doc_ref.get.return_value.exists = False

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value.document.return_value = mock_doc_ref
        from offerlens.storage.firestore import save_scored_offer

        offer_id = save_scored_offer(
            {"source": source, "url": url, "title": "Senior Dev", "score": 5},
            source=source,
            url=url,
        )

    mock_doc_ref.set.assert_called_once()
    assert offer_id == expected_id


def test_scanning_same_offer_twice_does_not_duplicate():
    """Scanner la même offre deux fois ne crée qu'un seul document Firestore."""
    source = "indeed"
    url = "https://indeed.com/viewjob?jk=dup"
    offer_data = {"source": source, "url": url, "title": "Dev", "score": 4}

    # First call: document does not exist → write
    mock_ref_first = MagicMock()
    mock_ref_first.get.return_value.exists = False
    # Second call: document already exists → skip
    mock_ref_second = MagicMock()
    mock_ref_second.get.return_value.exists = True

    with patch("offerlens.storage.firestore.get_client") as mock_client:
        mock_client.return_value.collection.return_value.document.side_effect = [
            mock_ref_first,
            mock_ref_second,
        ]
        from offerlens.storage.firestore import save_scored_offer

        save_scored_offer(offer_data, source=source, url=url)
        save_scored_offer(offer_data, source=source, url=url)

    mock_ref_first.set.assert_called_once()
    mock_ref_second.set.assert_not_called()
