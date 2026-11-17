"""Application operations for registration, login, profile, and PIN management."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import User
from app.security import create_access_token, hash_secret, verify_secret
from app.services.errors import ServiceError


def register(db: Session, name: str, email: str, password: str) -> User:
    normalized_email = email.lower()
    if db.scalar(select(User).where(User.email == normalized_email)):
        raise ServiceError(409, "E-mail já cadastrado")
    user = User(name=name, email=normalized_email, password_hash=hash_secret(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, username: str, password: str) -> str:
    user = db.scalar(select(User).where(User.email == username.lower()))
    if not user or not verify_secret(password, user.password_hash):
        raise ServiceError(401, "Credenciais inválidas")
    return create_access_token(user.id, user.role.value)


def update_profile(db: Session, user: User, name: str | None, profile) -> User:
    if name is not None:
        user.name = name
    if profile is not None:
        user.profile = profile
    db.commit()
    db.refresh(user)
    return user


def set_pin(db: Session, user: User, pin: str) -> None:
    user.pin_hash = hash_secret(pin)
    db.commit()
