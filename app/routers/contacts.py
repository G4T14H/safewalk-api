from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain.enums import ContactStatus
from app.domain.models import TrustedContact, User, utcnow
from app.schemas import ContactCreate, ContactOut
from app.security import new_token

router = APIRouter(prefix="/contacts", tags=["Contatos de confiança"])


@router.post("", response_model=ContactOut, status_code=201, summary="Convida um contato (fica pendente)")
def invite(data: ContactCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = TrustedContact(user_id=user.id, name=data.name, phone=data.phone, invite_token=new_token())
    db.add(contact)
    db.commit()
    return contact


@router.get("", response_model=list[ContactOut], summary="Lista meus contatos")
def list_contacts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(TrustedContact).where(TrustedContact.user_id == user.id)
                      .order_by(TrustedContact.id)).all()


@router.post("/accept/{invite_token}", response_model=ContactOut,
             summary="O contato aceita o convite (público, via link do convite)")
def accept(invite_token: str, db: Session = Depends(get_db)):
    contact = db.scalar(select(TrustedContact).where(TrustedContact.invite_token == invite_token))
    if not contact or contact.status == ContactStatus.revoked:
        raise HTTPException(404, "Convite inválido")
    contact.status = ContactStatus.accepted
    contact.accepted_at = utcnow()
    db.commit()
    return contact


@router.delete("/{contact_id}", status_code=204, summary="Remove um contato")
def remove(contact_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contact = db.get(TrustedContact, contact_id)
    if not contact or contact.user_id != user.id:
        raise HTTPException(404, "Contato não encontrado")
    db.delete(contact)
    db.commit()
