"""Application operations for mock camera data and the municipal dashboard."""
from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import INFRA_TYPES, ReportStatus, SOSStatus
from app.domain.models import Camera, Report, SOSAlert, utcnow
from app.schemas import CameraCreate, DashboardOut, CriticalPoint
from app.services.geo import haversine_m


def cameras_near(db: Session, lat: float, lng: float, radius_m: float) -> list[Camera]:
    return [camera for camera in db.scalars(select(Camera)).all()
            if haversine_m(lat, lng, camera.lat, camera.lng) <= radius_m]


def add_camera(db: Session, data: CameraCreate) -> Camera:
    camera = Camera(name=data.name, lat=data.lat, lng=data.lng, source=data.source)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def dashboard_overview(db: Session, days: int) -> DashboardOut:
    since = utcnow() - timedelta(days=days)
    reports = db.scalars(select(Report).where(Report.created_at >= since)).all()
    sos_count = db.scalar(select(func.count(SOSAlert.id)).where(
        SOSAlert.created_at >= since,
        SOSAlert.status.in_([SOSStatus.contacts_notified, SOSStatus.gcm_notified]))) or 0
    sp156_open = sum(1 for report in reports
                     if report.type in INFRA_TYPES and report.status == ReportStatus.active)
    groups: dict = defaultdict(list)
    for report in reports:
        groups[(round(report.lat, 3), round(report.lng, 3))].append(report)
    ranked = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)[:5]
    critical = [CriticalPoint(lat=point[0], lng=point[1], reports=len(rows),
                              predominant_type=Counter(r.type for r in rows).most_common(1)[0][0])
                for point, rows in ranked]
    return DashboardOut(period_days=days, reports_received=len(reports), sos_confirmed=sos_count,
                        sp156_open=sp156_open,
                        cameras_registered=db.scalar(select(func.count(Camera.id))) or 0,
                        critical_points=critical)
