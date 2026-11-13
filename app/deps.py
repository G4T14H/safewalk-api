"""Dependências de autenticação/autorização e rate limit."""
import time
from collections import defaultdict, deque

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.domain.enums import UserRole
from app.domain.models import User
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_operator(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.operator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a operadores da Prefeitura/GCM")
    return user


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """Limite simples em memória (req/min por IP). Em produção: Redis/API gateway."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas requisições. Tente novamente em instantes.")
    q.append(now)


def reset_rate_limit() -> None:
    _hits.clear()
