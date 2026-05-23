"""Configuration — chargement des variables d'environnement via pydantic-settings."""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "europe-west1"

    # LLM
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-4-5-20251001"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Embeddings
    embedding_model: str = "text-embedding-005"

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "offerlens-dev"

    # Gmail
    gmail_recipient: str = ""
    gmail_oauth_token_path: str = ""

    # Firestore
    firestore_emulator_host: str = ""


settings = Settings()
