from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import call_service, get_current_user, rate_limit
from app.domain.models import User
from app.schemas import PinSet, Token, UserCreate, UserOut, UserUpdate
from app.services import auth_service

router = APIRouter(tags=["Autenticação e usuário"])


@router.post("/auth/register", response_model=UserOut, status_code=201, dependencies=[Depends(rate_limit)],
             summary="Cadastra um cidadão")
def register(data: UserCreate, db: Session = Depends(get_db)):
    return call_service(auth_service.register, db, data.name, data.email, data.password)


@router.post("/auth/login", response_model=Token, dependencies=[Depends(rate_limit)],
             summary="Login (OAuth2 password; `username` = e-mail)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    token = call_service(auth_service.login, db, form.username, form.password)
    return Token(access_token=token)


@router.get("/users/me", response_model=UserOut, summary="Dados do usuário autenticado")
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/users/me", response_model=UserOut, summary="Atualiza nome e perfil de caminhada")
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return call_service(auth_service.update_profile, db, user, data.name, data.profile)


@router.put("/users/me/pin", status_code=204, summary="Define o PIN que cancela o SOS")
def set_pin(data: PinSet, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    call_service(auth_service.set_pin, db, user, data.pin)
