from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://vibedinsight:vibedinsight@localhost:5432/vibedinsight"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embedding_model: str = "mxbai-embed-large"  # 1024-dim, must match Vector(1024)

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Single shared secret for the whole API (single-user deployment).
    # Empty string disables auth — only acceptable for local development.
    api_key: str = ""

    # CORS - comma-separated list of allowed origins
    cors_origins: str = "*"

    # Ingest: allow fetching URLs that resolve to private/loopback addresses
    # (enable if you want to save pages from your own LAN/homeserver)
    allow_private_urls: bool = False

    # Semantic similarity: minimum cosine similarity for a SIMILAR relation
    similarity_threshold: float = 0.75

    # RAG chat ("Frag dein Archiv"): retrieval + context budget.
    # rag_min_similarity is deliberately lower than similarity_threshold — a
    # short question rarely matches a document as strongly as two documents
    # match each other, so a lenient floor keeps recall useful.
    #
    # Budgets are tuned for a CPU-only VPS: shorter prompts and a capped answer
    # length (rag_num_predict) keep latency reasonable with small models.
    rag_top_k: int = 4
    rag_min_similarity: float = 0.2
    rag_context_char_budget: int = 3000
    rag_num_predict: int = 200  # max answer tokens (Ollama num_predict); 0 = model default

    # Auto-generate the weekly summary every Sunday evening (server time)
    weekly_auto_generate: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
