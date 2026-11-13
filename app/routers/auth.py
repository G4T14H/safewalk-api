from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, rate_limit
from app.domain.models import User
from app.schemas import PinSet, Token, UserCreate, UserOut, UserUpdate
from app.security import create_access_token, hash_secret, verify_secret

router = APIRouter(tags=["Autenticação e usuário"])


@router.post("/auth/register", response_model=UserOut, status_code=201, dependencies=[Depends(rate_limit)],
             summary="Cadastra um cidadão")
def register(data: UserCreate, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(name=data.name, email=email, password_hash=hash_secret(data.password))
    db.add(user)
    db.commit()
    return user


@router.post("/auth/login", response_model=Token, dependencies=[Depends(rate_limit)],
             summary="Login (OAuth2 password; `username` = e-mail)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_secret(form.password, user.password_hash):
        raise HTTPException(401, "Credenciais inválidas")
    return Token(access_token=create_access_token(user.id, user.role.value))


@router.get("/users/me", response_model=UserOut, summary="Dados do usuário autenticado")
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/users/me", response_model=UserOut, summary="Atualiza nome e perfil de caminhada")
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.name is not None:
        user.name = data.name
    if data.profile is not None:
        user.profile = data.profile
    db.commit()
    return user


@router.put("/users/me/pin", status_code=204, summary="Define o PIN que cancela o SOS")
def set_pin(data: PinSet, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.pin_hash = hash_secret(data.pin)
    db.commit()
