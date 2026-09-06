"""
Application configuration
Handles environment variables and settings
"""
import os
from typing import Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Stonks API"
    
    # Database Configuration
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "stonks")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "stonks_password_change_me")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "stonks")
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from components"""
        return f"postgresql://{self.POSTGRES_USER}:{quote_plus(self.POSTGRES_PASSWORD)}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis Configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

    @property
    def REDIS_URL(self) -> str:
        """Construct Redis URL from components"""
        if self.REDIS_PASSWORD:
            return f"redis://:{quote_plus(self.REDIS_PASSWORD)}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Celery Configuration
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "")
    
    @property
    def CELERY_BROKER(self) -> str:
        """Get Celery broker URL, fallback to Redis URL"""
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    @property 
    def CELERY_BACKEND(self) -> str:
        """Get Celery result backend, fallback to Redis URL"""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL
    
    # LLM Configuration (Optional)
    ANALYTICS_LLM_PROVIDER: str = os.getenv("ANALYTICS_LLM_PROVIDER", "none")  # none | openai | ollama
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    # Stronger model for the desk's decision tier (research manager / trader /
    # portfolio manager). Falls back to OLLAMA_MODEL when unset.
    OLLAMA_DEEP_MODEL: str = os.getenv("OLLAMA_DEEP_MODEL", "")
    
    # External API Keys
    ALPHA_VANTAGE_API_KEY: Optional[str] = os.getenv("ALPHA_VANTAGE_API_KEY")
    POLYGON_API_KEY: Optional[str] = os.getenv("POLYGON_API_KEY")

    # Reddit OAuth (app-only / client-credentials). Without these the WSB
    # ingestion falls back to the public JSON endpoint, which Reddit 403-blocks
    # from datacenter IPs: fine for local dev, dead in k8s.
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "Stonks-Analytics/1.0 (Educational Research)")

    # SEC EDGAR fair-access policy asks for a contact address in the User-Agent.
    SEC_CONTACT_EMAIL: str = os.getenv("SEC_CONTACT_EMAIL", "")

    # Security / Auth
    API_KEY: Optional[str] = os.getenv("API_KEY")
    ENABLE_RATE_LIMIT: bool = os.getenv("ENABLE_RATE_LIMIT", "true").lower() == "true"
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

    # OIDC / Authentik configuration (Public client with PKCE: no client secret needed)
    OIDC_ISSUER_URL: Optional[str] = os.getenv("OIDC_ISSUER_URL")  # e.g. https://auth.example.com/application/o/stonks/
    OIDC_CLIENT_ID: Optional[str] = os.getenv("OIDC_CLIENT_ID")
    OIDC_AUDIENCE: str = os.getenv("OIDC_AUDIENCE", "")  # defaults to OIDC_CLIENT_ID if empty
    # Comma-separated list of emails that receive admin role on first login
    ADMIN_EMAILS: str = os.getenv("ADMIN_EMAILS", "")

    # CORS: comma-separated production origins (e.g. "https://stonks.example.com")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")

    # Brokerage (per-user Alpaca accounts)
    # Fernet key for encrypting user broker API credentials at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    BROKER_CREDS_ENCRYPTION_KEY: Optional[str] = os.getenv("BROKER_CREDS_ENCRYPTION_KEY")
    # Global trading halt: when true, all order placement is rejected regardless of per-user settings.
    BROKER_TRADING_HALTED: bool = os.getenv("BROKER_TRADING_HALTED", "false").lower() == "true"

    # Signal plugin configuration: JSON object mapping source id to that source's
    # config (tracked figures, curated lists, keys). Per-deployment admin
    # settings stored in the database override these values key by key.
    SIGNAL_SOURCE_CONFIG: str = os.getenv("SIGNAL_SOURCE_CONFIG", "")
    
    # Application Configuration
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Server Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8080"))

    # extra="ignore": .env also carries docker-compose/frontend-only variables
    # (VITE_*, OLLAMA_DOCKER_*) that aren't backend settings.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


# Global settings instance
settings = Settings()
