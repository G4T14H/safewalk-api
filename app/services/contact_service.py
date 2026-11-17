"""Application operations for trusted-contact consent and lifecycle."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ContactStatus
from app.domain.models import TrustedContact, User, utcnow
from app.security import new_token
from app.services.errors import ServiceError


def invite(db: Session, user: User, name: str, phone: str) -> TrustedContact:
    contact = TrustedContact(user_id=user.id, name=name, phone=phone, invite_token=new_token())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def list_contacts(db: Session, user_id: int) -> list[TrustedContact]:
    return db.scalars(select(TrustedContact).where(TrustedContact.user_id == user_id)
                      .order_by(TrustedContact.id)).all()


def accept_invite(db: Session, invite_token: str) -> TrustedContact:
    contact = db.scalar(select(TrustedContact).where(TrustedContact.invite_token == invite_token))
    if not contact or contact.status == ContactStatus.revoked:
        raise ServiceError(404, "Convite inválido")
    contact.status = ContactStatus.accepted
    contact.accepted_at = utcnow()
    db.commit()
    db.refresh(contact)
    return contact


def remove(db: Session, contact_id: int, user_id: int) -> None:
    contact = db.get(TrustedContact, contact_id)
    if not contact or contact.user_id != user_id:
        raise ServiceError(404, "Contato não encontrado")
    db.delete(contact)
    db.commit()
