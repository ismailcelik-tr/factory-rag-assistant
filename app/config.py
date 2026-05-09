from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "gemma4:e4b"
    embedding_model: str = "nomic-embed-text"

    # LLM generation
    llm_temperature: float = 0.1
    llm_max_tokens: int = 600

    # Retrieval
    top_k: int = 5
    max_context_tokens: int = 3000

    # Paths (relative to project root; resolved by each module at call time)
    raw_docs_path: str = "data/raw/"
    embeddings_path: str = "data/embeddings/"
    processed_path: str = "data/processed/"

    # ChromaDB
    collection_name: str = "factory_docs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
