from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import call_service, get_current_user, require_operator
from app.domain.models import User
from app.schemas import ReportCreate, ReportOut, ReportResolve
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Relatos colaborativos"])


@router.post("", response_model=ReportOut, status_code=201, summary="Cria um relato (entra com peso baixo)")
def create(data: ReportCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return call_service(report_service.create_report, db, user, data.type, data.lat, data.lng,
                        data.details, data.anonymous)


@router.get("", response_model=list[ReportOut], summary="Relatos ativos num raio (autor nunca é exposto)")
def nearby(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
           radius_m: float = Query(1000, gt=0, le=10000), user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    return call_service(report_service.nearby_reports, db, lat, lng, radius_m)


@router.post("/{report_id}/confirm", response_model=ReportOut, summary="Confirma um relato de outra pessoa")
def confirm(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return call_service(report_service.confirm_report, db, report_id, user)


@router.patch("/{report_id}/resolve", response_model=ReportOut,
              summary="Operador encerra o relato (resolvido no SP156) ou marca como falso")
def resolve(report_id: int, data: ReportResolve, op: User = Depends(require_operator),
            db: Session = Depends(get_db)):
    return call_service(report_service.resolve_report, db, report_id, data.status)


@router.delete("/{report_id}", status_code=204, summary="Autor apaga o próprio relato")
def delete(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    call_service(report_service.delete_report, db, report_id, user.id)
