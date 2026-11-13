"""Configurações da aplicação (lidas de variáveis de ambiente)."""
import os


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./safewalk.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production-32b!")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "120"))
    # Escalada do SOS (segundos)
    SOS_ASK_TIMEOUT_SECONDS: int = int(os.getenv("SOS_ASK_TIMEOUT_SECONDS", "30"))
    SOS_CONTACT_TIMEOUT_SECONDS: int = int(os.getenv("SOS_CONTACT_TIMEOUT_SECONDS", "120"))
    # Rate limit simples nos endpoints de autenticação (req/min por IP)
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))


settings = Settings()
