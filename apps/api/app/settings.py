from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI
    openai_api_key: str = Field(validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL")
    openai_store: bool = Field(default=False, validation_alias="OPENAI_STORE")

    # Ollama (local / free)
    ollama_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_URL")
    ollama_model: str = Field(default="llama3.1", validation_alias="OLLAMA_MODEL")
    ollama_embedding_model: str = Field(default="nomic-embed-text", validation_alias="OLLAMA_EMBEDDING_MODEL")

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    qdrant_collection: str = Field(default="booking_kb", validation_alias="QDRANT_COLLECTION")

    # Retrieval
    top_k: int = Field(default=5, validation_alias="TOP_K")
    min_score: float = Field(default=0.22, validation_alias="MIN_SCORE")

    # Chunking
    chunk_size: int = Field(default=900, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=180, validation_alias="CHUNK_OVERLAP")


settings = Settings()
