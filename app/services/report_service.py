"""Regras dos relatos colaborativos: peso progressivo, validade e antiabuso."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import CRIME_TYPES, INFRA_TYPES, ReportStatus, ReportType
from app.domain.models import Report, utcnow
from app.services.geo import haversine_m

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
