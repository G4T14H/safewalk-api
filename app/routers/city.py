"""Endpoints B2G: câmeras (Smart Sampa, mock) e painel da Prefeitura."""
from collections import Counter, defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_operator
from app.domain.enums import INFRA_TYPES, ReportStatus, SOSStatus
from app.domain.models import Camera, Report, SOSAlert, User, utcnow
from app.schemas import CameraCreate, CameraOut, CriticalPoint, DashboardOut
from app.services.geo import haversine_m

router = APIRouter(tags=["Prefeitura / Smart Sampa"])


@router.get("/cameras", response_model=list[CameraOut], summary="Câmeras num raio (só posição; sem imagem)")
def cameras(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
            radius_m: float = Query(1000, gt=0, le=10000), user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    return [c for c in db.scalars(select(Camera)).all() if haversine_m(lat, lng, c.lat, c.lng) <= radius_m]


@router.post("/cameras", response_model=CameraOut, status_code=201, summary="Cadastra câmera (operador)")
def add_camera(data: CameraCreate, op: User = Depends(require_operator), db: Session = Depends(get_db)):
    cam = Camera(name=data.name, lat=data.lat, lng=data.lng, source=data.source)
    db.add(cam)
    db.commit()
    return cam


@router.get("/dashboard/overview", response_model=DashboardOut,
            summary="Painel da Prefeitura: relatos, SOS, chamados SP156 e pontos críticos")
def overview(days: int = Query(7, ge=1, le=90), op: User = Depends(require_operator), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=days)
    reports = db.scalars(select(Report).where(Report.created_at >= since)).all()
    sos = db.scalar(select(func.count(SOSAlert.id)).where(
        SOSAlert.created_at >= since,
        SOSAlert.status.in_([SOSStatus.contacts_notified, SOSStatus.gcm_notified]))) or 0
    sp156_open = sum(1 for r in reports if r.type in INFRA_TYPES and r.status == ReportStatus.active)
    groups: dict = defaultdict(list)
    for r in reports:
        groups[(round(r.lat, 3), round(r.lng, 3))].append(r)
    ranked = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)[:5]
    critical = [CriticalPoint(lat=k[0], lng=k[1], reports=len(v),
                              predominant_type=Counter(r.type for r in v).most_common(1)[0][0])
                for k, v in ranked]
    return DashboardOut(period_days=days, reports_received=len(reports), sos_confirmed=sos, sp156_open=sp156_open,
                        cameras_registered=db.scalar(select(func.count(Camera.id))) or 0, critical_points=critical)
