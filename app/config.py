"""Configurações da aplicação (lidas de variáveis de ambiente)."""
import os
import secrets
from pathlib import Path


def _load_dotenv(path: Path = Path(__file__).resolve().parent.parent / ".env") -> None:
    """Carrega o arquivo .env (se existir) sem sobrescrever variáveis já definidas no ambiente."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()


APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
_production = APP_ENV in {"prod", "production"}
_secret_key = os.getenv("SECRET_KEY", "").strip()
if _production and len(_secret_key) < 32:
    raise RuntimeError("SECRET_KEY must contain at least 32 characters when APP_ENV=production")
if not _secret_key:
    # A random per-process key is safe for local demos; tokens are invalidated on restart.
    _secret_key = secrets.token_urlsafe(48)

_seed_demo_users = os.getenv("SEED_DEMO_USERS", "").strip().lower()
if not _seed_demo_users:
    _seed_demo_users = "false" if _production else "true"
if _production and _seed_demo_users in {"1", "true", "yes", "on"}:
    raise RuntimeError("SEED_DEMO_USERS must be disabled when APP_ENV=production")


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./safewalk.db")
    APP_ENV: str = APP_ENV
    SECRET_KEY: str = _secret_key
    SEED_DEMO_USERS: bool = _seed_demo_users in {"1", "true", "yes", "on"}
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "120"))
    # Escalada do SOS (segundos)
    SOS_ASK_TIMEOUT_SECONDS: int = int(os.getenv("SOS_ASK_TIMEOUT_SECONDS", "30"))
    SOS_CONTACT_TIMEOUT_SECONDS: int = int(os.getenv("SOS_CONTACT_TIMEOUT_SECONDS", "120"))
    # Rate limit simples nos endpoints de autenticação (req/min por IP)
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))


settings = Settings()
