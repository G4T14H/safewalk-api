"""Regras dos relatos colaborativos: peso progressivo, validade e antiabuso."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import CRIME_TYPES, INFRA_TYPES, ReportStatus, ReportType
from app.domain.models import Report, ReportConfirmation, User, utcnow
from app.services.geo import haversine_m
from app.services.errors import ServiceError

DUPLICATE_RADIUS_M = 100.0
DUPLICATE_WINDOW = timedelta(minutes=30)
SPAM_LIMIT = 5
SPAM_WINDOW = timedelta(minutes=10)
CONFIRM_BONUS = 0.15
REPUTATION_STEP = 0.02


def initial_weight(reputation: float) -> float:
    return round(0.2 + 0.2 * reputation, 3)


def expiry_for(rtype: ReportType):
    """Assalto/assédio: horas. Alagamento: até 12h. Calçada/iluminação/obra: até o SP156 resolver."""
    now = utcnow()
    if rtype in CRIME_TYPES:
        return now + timedelta(hours=6)
    if rtype == ReportType.alagamento:
        return now + timedelta(hours=12)
    return None


def needs_sp156(rtype: ReportType) -> bool:
    return rtype in INFRA_TYPES


def active_reports(db: Session) -> list[Report]:
    now = utcnow()
    rows = db.scalars(select(Report).where(Report.status == ReportStatus.active)).all()
    out = []
    for r in rows:
        if r.expires_at is not None and r.expires_at <= now:
            r.status = ReportStatus.expired
        else:
            out.append(r)
    db.flush()
    return out


def find_duplicate(db: Session, author_id: int, rtype: ReportType, lat: float, lng: float):
    since = utcnow() - DUPLICATE_WINDOW
    rows = db.scalars(select(Report).where(
        Report.author_id == author_id, Report.type == rtype, Report.created_at >= since)).all()
    return next((r for r in rows if haversine_m(lat, lng, r.lat, r.lng) <= DUPLICATE_RADIUS_M), None)


def is_spamming(db: Session, author_id: int) -> bool:
    since = utcnow() - SPAM_WINDOW
    n = len(db.scalars(select(Report.id).where(Report.author_id == author_id, Report.created_at >= since)).all())
    return n >= SPAM_LIMIT


def nearby_reports(db: Session, lat: float, lng: float, radius_m: float) -> list[Report]:
    rows = [r for r in active_reports(db) if haversine_m(lat, lng, r.lat, r.lng) <= radius_m]
    db.commit()
    return rows


def create_report(db: Session, user: User, rtype: ReportType, lat: float, lng: float,
                  details: str | None, anonymous: bool) -> Report:
    if is_spamming(db, user.id):
        raise ServiceError(429, "Limite de relatos atingido. Aguarde alguns minutos.")
    if find_duplicate(db, user.id, rtype, lat, lng):
        raise ServiceError(409, "Relato duplicado: você já relatou isto aqui recentemente")
    report = Report(author_id=user.id, type=rtype, lat=lat, lng=lng, details=details,
                    anonymous=anonymous, weight=initial_weight(user.reputation), expires_at=expiry_for(rtype))
    db.add(report)
    db.flush()
    if needs_sp156(rtype):
        report.sp156_protocol = f"SP156-{104000 + report.id}"
    db.commit()
    db.refresh(report)
    return report


def confirm_report(db: Session, report_id: int, user: User) -> Report:
    report = db.get(Report, report_id)
    if not report or report.status != ReportStatus.active:
        raise ServiceError(404, "Relato não encontrado ou inativo")
    if report.author_id == user.id:
        raise ServiceError(400, "Você não pode confirmar o próprio relato")
    if any(confirmation.user_id == user.id for confirmation in report.confirmations):
        raise ServiceError(409, "Você já confirmou este relato")
    report.confirmations.append(ReportConfirmation(user_id=user.id))
    report.weight = round(min(1.0, report.weight + CONFIRM_BONUS), 3)
    author = db.get(User, report.author_id)
    if author is None:
        raise ServiceError(404, "Autor do relato não encontrado")
    author.reputation = round(min(1.0, author.reputation + REPUTATION_STEP), 3)
    db.commit()
    db.refresh(report)
    return report


def resolve_report(db: Session, report_id: int, status: ReportStatus) -> Report:
    if status not in (ReportStatus.resolved, ReportStatus.false_report):
        raise ServiceError(422, "status deve ser 'resolved' ou 'false_report'")
    report = db.get(Report, report_id)
    if not report:
        raise ServiceError(404, "Relato não encontrado")
    report.status = status
    if status == ReportStatus.false_report:
        author = db.get(User, report.author_id)
        if author is not None:
            author.reputation = round(max(0.0, author.reputation - 0.2), 3)
    db.commit()
    db.refresh(report)
    return report


def delete_report(db: Session, report_id: int, user_id: int) -> None:
    report = db.get(Report, report_id)
    if not report or report.author_id != user_id:
        raise ServiceError(404, "Relato não encontrado")
    db.delete(report)
    db.commit()
