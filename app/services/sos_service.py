"""Escalada do SOS: pergunta -> contatos -> central da GCM (simulada)."""
from datetime import timedelta

from app.config import settings
from app.domain.enums import SOSStatus, SOSTrigger
from app.domain.models import SOSAlert, utcnow


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
