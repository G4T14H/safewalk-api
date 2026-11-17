from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import call_service, get_current_user
from app.domain.models import User
from app.schemas import ContactCreate, ContactOut
from app.services import contact_service

router = APIRouter(prefix="/contacts", tags=["Contatos de confiança"])


@router.post("", response_model=ContactOut, status_code=201, summary="Convida um contato (fica pendente)")
def invite(data: ContactCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return call_service(contact_service.invite, db, user, data.name, data.phone)


@router.get("", response_model=list[ContactOut], summary="Lista meus contatos")
def list_contacts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return call_service(contact_service.list_contacts, db, user.id)


@router.post("/accept/{invite_token}", response_model=ContactOut,
             summary="O contato aceita o convite (público, via link do convite)")
def accept(invite_token: str, db: Session = Depends(get_db)):
    return call_service(contact_service.accept_invite, db, invite_token)


@router.delete("/{contact_id}", status_code=204, summary="Remove um contato")
def remove(contact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    call_service(contact_service.remove, db, contact_id, user.id)
