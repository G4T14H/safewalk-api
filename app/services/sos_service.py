"""Escalada do SOS: pergunta -> contatos -> central da GCM (simulada)."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.enums import SOSStatus, SOSTrigger
from app.domain.models import SOSAlert, Trip, User, utcnow
from app.security import verify_secret
from app.services.errors import ServiceError


def start(user_id, trip_id, trigger: SOSTrigger, lat, lng) -> SOSAlert:
    now = utcnow()
    alert = SOSAlert(user_id=user_id, trip_id=trip_id, trigger=trigger, lat=lat, lng=lng, created_at=now,
                     status=SOSStatus.asking)
    if trigger == SOSTrigger.button:  # botão = pedido explícito, pula a pergunta "Tudo bem?"
        alert.status = SOSStatus.contacts_notified
        alert.contacts_notified_at = now
    return alert


def advance(alert: SOSAlert, now=None) -> SOSAlert:
    """Aplica as escalas automáticas por tempo decorrido (idempotente)."""
    now = now or utcnow()
    if alert.status == SOSStatus.asking:
        ask_end = alert.created_at + timedelta(seconds=settings.SOS_ASK_TIMEOUT_SECONDS)
        if now >= ask_end:
            alert.status = SOSStatus.contacts_notified
            alert.contacts_notified_at = ask_end
    if alert.status == SOSStatus.contacts_notified:
        gcm_at = alert.contacts_notified_at + timedelta(seconds=settings.SOS_CONTACT_TIMEOUT_SECONDS)
        if now >= gcm_at:
            _to_gcm(alert, gcm_at)
    return alert


def _to_gcm(alert: SOSAlert, at) -> None:
    alert.status = SOSStatus.gcm_notified
    alert.gcm_notified_at = at
    alert.gcm_protocol = f"GCM-{alert.id or 0:06d}"


def escalate(alert: SOSAlert) -> SOSAlert:
    now = utcnow()
    if alert.status == SOSStatus.asking:
        alert.status = SOSStatus.contacts_notified
        alert.contacts_notified_at = now
    elif alert.status == SOSStatus.contacts_notified:
        _to_gcm(alert, now)
    return alert


def timeline(alert: SOSAlert) -> list[dict]:
    ev = [{"event": "Alerta disparado" if alert.trigger == SOSTrigger.button else "Pergunta 'Tudo bem?' enviada",
           "at": alert.created_at}]
    if alert.contacts_notified_at:
        ev.append({"event": "Contatos receberam a localização", "at": alert.contacts_notified_at})
    if alert.gcm_notified_at:
        ev.append({"event": f"Central da GCM acionada (protocolo {alert.gcm_protocol})", "at": alert.gcm_notified_at})
    if alert.cancelled_at:
        ev.append({"event": "Cancelado com PIN", "at": alert.cancelled_at})
    return ev


def create_alert(db: Session, user_id: int, trip_id: int | None, trigger: SOSTrigger, lat: float, lng: float) -> SOSAlert:
    if trip_id is not None:
        trip = db.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            raise ServiceError(404, "Trajeto não encontrado")
    alert = start(user_id, trip_id, trigger, lat, lng)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def _owned_alert(db: Session, alert_id: int, user_id: int) -> SOSAlert:
    alert = db.get(SOSAlert, alert_id)
    if not alert or alert.user_id != user_id:
        raise ServiceError(404, "Alerta não encontrado")
    return alert


def list_alerts(db: Session, user_id: int) -> list[SOSAlert]:
    alerts = db.scalars(select(SOSAlert).where(SOSAlert.user_id == user_id)
                        .order_by(SOSAlert.id.desc())).all()
    for alert in alerts:
        advance(alert)
    db.commit()
    return alerts


def get_alert(db: Session, alert_id: int, user_id: int) -> SOSAlert:
    alert = advance(_owned_alert(db, alert_id, user_id))
    db.commit()
    return alert


def escalate_alert(db: Session, alert_id: int, user_id: int) -> SOSAlert:
    alert = advance(_owned_alert(db, alert_id, user_id))
    if alert.status == SOSStatus.cancelled:
        raise ServiceError(409, "Alerta já cancelado")
    if alert.status == SOSStatus.gcm_notified:
        raise ServiceError(409, "A central da GCM já foi acionada")
    escalate(alert)
    db.commit()
    return alert


def cancel_alert(db: Session, alert_id: int, user_id: int, pin: str) -> SOSAlert:
    alert = _owned_alert(db, alert_id, user_id)
    if alert.status == SOSStatus.cancelled:
        raise ServiceError(409, "Alerta já cancelado")
    user = db.get(User, user_id)
    if not user or not user.has_pin:
        raise ServiceError(400, "Defina um PIN em PUT /users/me/pin")
    if not verify_secret(pin, user.pin_hash):
        raise ServiceError(403, "PIN incorreto")
    alert.status = SOSStatus.cancelled
    alert.cancelled_at = utcnow()
    db.commit()
    return alert
