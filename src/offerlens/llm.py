"""Initialisation LLM et embeddings — abstraction LangChain swappable via env vars."""

from google import genai
from google.genai import types
from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings

from offerlens.config import settings


def get_chat_model():
    kwargs: dict = {}
    if settings.llm_provider == "google_vertexai":
        kwargs["project"] = settings.gcp_project_id
        kwargs["location"] = settings.llm_location
    return init_chat_model(settings.llm_model, model_provider=settings.llm_provider, **kwargs)


class VertexEmbeddings(Embeddings):
    """Embeddings via google-genai SDK (Vertex AI backend) — text-embedding-005."""

    def __init__(self, model_name: str, project: str, location: str):
        self._client = genai.Client(vertexai=True, project=project, location=location)
        self._model = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=texts,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return [e.values for e in response.embeddings]

    def embed_query(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=[text],
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return response.embeddings[0].values


def get_embeddings() -> Embeddings:
    return VertexEmbeddings(
        model_name=settings.embedding_model,
        project=settings.gcp_project_id,
        location=settings.gcp_region,
    )
