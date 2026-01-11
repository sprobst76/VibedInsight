import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://vibedinsight:vibedinsight@localhost:5432/vibedinsight"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # CORS - comma-separated list of allowed origins
    cors_origins: str = "*"

    # JWT Authentication
    # IMPORTANT: Set JWT_SECRET_KEY in .env for production!
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    jwt_secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Security
    # Minimum password length for user accounts
    min_password_length: int = 8

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
