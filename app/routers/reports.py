from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_operator
from app.domain.enums import ReportStatus
from app.domain.models import Report, ReportConfirmation, User
from app.schemas import ReportCreate, ReportOut, ReportResolve
from app.services import report_service
from app.services.geo import haversine_m

router = APIRouter(prefix="/reports", tags=["Relatos colaborativos"])


@router.post("", response_model=ReportOut, status_code=201, summary="Cria um relato (entra com peso baixo)")
def create(data: ReportCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if report_service.is_spamming(db, user.id):
        raise HTTPException(429, "Limite de relatos atingido. Aguarde alguns minutos.")
    if report_service.find_duplicate(db, user.id, data.type, data.lat, data.lng):
        raise HTTPException(409, "Relato duplicado: você já relatou isto aqui recentemente")
    report = Report(author_id=user.id, type=data.type, lat=data.lat, lng=data.lng, details=data.details,
                    anonymous=data.anonymous, weight=report_service.initial_weight(user.reputation),
                    expires_at=report_service.expiry_for(data.type))
    db.add(report)
    db.flush()
    if report_service.needs_sp156(data.type):
        report.sp156_protocol = f"SP156-{104000 + report.id}"  # chamado fictício (integração simulada)
    db.commit()
    return report


@router.get("", response_model=list[ReportOut], summary="Relatos ativos num raio (autor nunca é exposto)")
def nearby(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
           radius_m: float = Query(1000, gt=0, le=10000), user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    rows = [r for r in report_service.active_reports(db) if haversine_m(lat, lng, r.lat, r.lng) <= radius_m]
    db.commit()
    return rows


@router.post("/{report_id}/confirm", response_model=ReportOut, summary="Confirma um relato de outra pessoa")
def confirm(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report or report.status != ReportStatus.active:
        raise HTTPException(404, "Relato não encontrado ou inativo")
    if report.author_id == user.id:
        raise HTTPException(400, "Você não pode confirmar o próprio relato")
    if any(c.user_id == user.id for c in report.confirmations):
        raise HTTPException(409, "Você já confirmou este relato")
    report.confirmations.append(ReportConfirmation(user_id=user.id))
    report.weight = round(min(1.0, report.weight + report_service.CONFIRM_BONUS), 3)
    author = db.get(User, report.author_id)
    author.reputation = round(min(1.0, author.reputation + report_service.REPUTATION_STEP), 3)
    db.commit()
    return report


@router.patch("/{report_id}/resolve", response_model=ReportOut,
              summary="Operador encerra o relato (resolvido no SP156) ou marca como falso")
def resolve(report_id: int, data: ReportResolve, op: User = Depends(require_operator),
            db: Session = Depends(get_db)):
    if data.status not in (ReportStatus.resolved, ReportStatus.false_report):
        raise HTTPException(422, "status deve ser 'resolved' ou 'false_report'")
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Relato não encontrado")
    report.status = data.status
    if data.status == ReportStatus.false_report:
        author = db.get(User, report.author_id)
        author.reputation = round(max(0.0, author.reputation - 0.2), 3)
    db.commit()
    return report


@router.delete("/{report_id}", status_code=204, summary="Autor apaga o próprio relato")
def delete(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report or report.author_id != user.id:
        raise HTTPException(404, "Relato não encontrado")
    db.delete(report)
    db.commit()
