from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import call_service, get_current_user
from app.domain.models import SOSAlert, User
from app.schemas import SOSCancel, SOSCreate, SOSOut
from app.services import sos_service

router = APIRouter(prefix="/sos", tags=["SOS"])


def _out(alert: SOSAlert) -> SOSOut:
    return SOSOut(id=alert.id, status=alert.status, trigger=alert.trigger, lat=alert.lat, lng=alert.lng,
                  gcm_protocol=alert.gcm_protocol, created_at=alert.created_at,
                  timeline=sos_service.timeline(alert))


@router.post("", response_model=SOSOut, status_code=201,
             summary="Dispara SOS (botão avisa contatos na hora; gatilhos automáticos perguntam 'Tudo bem?' por 30 s)")
def trigger(data: SOSCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = call_service(sos_service.create_alert, db, user.id, data.trip_id, data.trigger, data.lat, data.lng)
    return _out(alert)


@router.get("", response_model=list[SOSOut], summary="Meus alertas")
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alerts = call_service(sos_service.list_alerts, db, user.id)
    return [_out(alert) for alert in alerts]


@router.get("/{alert_id}", response_model=SOSOut, summary="Estado do alerta (aplica a escalada por tempo)")
def get_alert(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(call_service(sos_service.get_alert, db, alert_id, user.id))


@router.post("/{alert_id}/escalate", response_model=SOSOut, summary="Escala imediatamente para a próxima etapa")
def escalate(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(call_service(sos_service.escalate_alert, db, alert_id, user.id))


@router.post("/{alert_id}/cancel", response_model=SOSOut, summary="Cancela o alerta — somente com o PIN correto")
def cancel(alert_id: int, data: SOSCancel, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(call_service(sos_service.cancel_alert, db, alert_id, user.id, data.pin))
