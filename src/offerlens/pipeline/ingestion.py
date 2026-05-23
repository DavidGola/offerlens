"""Ingestion CV — PDF → chunks → embeddings Vertex AI → Firestore cv_chunks."""

from pathlib import Path

from google.cloud import firestore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from offerlens.config import settings
from offerlens.llm import get_embeddings


def load_cv_from_pdf(path: str | Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_cv(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_text(text)


def ingest_cv(path: str | Path) -> int:
    """Charge le CV PDF, génère les embeddings et persiste dans Firestore cv_chunks.
    Retourne le nombre de chunks ingérés.
    """
    text = load_cv_from_pdf(path)
    chunks = chunk_cv(text)

    embeddings = get_embeddings()
    db = firestore.Client(project=settings.gcp_project_id)
    collection = db.collection("cv_chunks")

    # Supprime les chunks existants avant de réingérer
    for doc in collection.stream():
        doc.reference.delete()

    vectors = embeddings.embed_documents(chunks)

    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        collection.document(f"chunk_{i:03d}").set({
            "content": chunk,
            "embedding": vector,
            "source": "cv",
            "index": i,
        })

    return len(chunks)
