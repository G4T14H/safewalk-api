from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain.enums import SOSStatus
from app.domain.models import SOSAlert, Trip, User, utcnow
from app.schemas import SOSCancel, SOSCreate, SOSOut
from app.security import verify_secret
from app.services import sos_service

router = APIRouter(prefix="/sos", tags=["SOS"])


def _out(a: SOSAlert) -> SOSOut:
    return SOSOut(id=a.id, status=a.status, trigger=a.trigger, lat=a.lat, lng=a.lng, gcm_protocol=a.gcm_protocol,
                  created_at=a.created_at, timeline=sos_service.timeline(a))


def _own(db: Session, alert_id: int, user: User) -> SOSAlert:
    alert = db.get(SOSAlert, alert_id)
    if not alert or alert.user_id != user.id:
        raise HTTPException(404, "Alerta não encontrado")
    return alert


@router.post("", response_model=SOSOut, status_code=201,
             summary="Dispara SOS (botão avisa contatos na hora; gatilhos automáticos perguntam 'Tudo bem?' por 30 s)")
def trigger(data: SOSCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.trip_id is not None:
        trip = db.get(Trip, data.trip_id)
        if not trip or trip.user_id != user.id:
            raise HTTPException(404, "Trajeto não encontrado")
    alert = sos_service.start(user.id, data.trip_id, data.trigger, data.lat, data.lng)
    db.add(alert)
    db.commit()
    return _out(alert)


@router.get("", response_model=list[SOSOut], summary="Meus alertas")
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alerts = db.scalars(select(SOSAlert).where(SOSAlert.user_id == user.id).order_by(SOSAlert.id.desc())).all()
    for a in alerts:
        sos_service.advance(a)
    db.commit()
    return [_out(a) for a in alerts]


@router.get("/{alert_id}", response_model=SOSOut, summary="Estado do alerta (aplica a escalada por tempo)")
def get_alert(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = sos_service.advance(_own(db, alert_id, user))
    db.commit()
    return _out(alert)


@router.post("/{alert_id}/escalate", response_model=SOSOut, summary="Escala imediatamente para a próxima etapa")
def escalate(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = sos_service.advance(_own(db, alert_id, user))
    if alert.status == SOSStatus.cancelled:
        raise HTTPException(409, "Alerta já cancelado")
    if alert.status == SOSStatus.gcm_notified:
        raise HTTPException(409, "A central da GCM já foi acionada")
    sos_service.escalate(alert)
    db.commit()
    return _out(alert)


@router.post("/{alert_id}/cancel", response_model=SOSOut, summary="Cancela o alerta — somente com o PIN correto")
def cancel(alert_id: int, data: SOSCancel, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = _own(db, alert_id, user)
    if alert.status == SOSStatus.cancelled:
        raise HTTPException(409, "Alerta já cancelado")
    if not user.has_pin:
        raise HTTPException(400, "Defina um PIN em PUT /users/me/pin")
    if not verify_secret(data.pin, user.pin_hash):
        raise HTTPException(403, "PIN incorreto")
    alert.status = SOSStatus.cancelled
    alert.cancelled_at = utcnow()
    db.commit()
    return _out(alert)
