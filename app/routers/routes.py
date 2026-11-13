from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain.enums import WalkProfile
from app.domain.models import Camera, RiskHotspot, User
from app.schemas import RiskScoreOut, RouteCompareIn, RouteCompareOut, RouteOption
from app.services import report_service, risk_service
from app.services.timeutil import local_hour

router = APIRouter(tags=["Rotas e risco"])

def _local_hour(depart_at) -> int:
    return local_hour(depart_at)


def _data(db: Session):
    return (db.scalars(select(RiskHotspot)).all(), report_service.active_reports(db),
            db.scalars(select(Camera)).all())


def _option(r: risk_service.RouteResult) -> RouteOption:
    return RouteOption(kind=r.kind, distance_m=r.distance_m, duration_min=r.duration_min, risk_score=r.score,
                       risk_level=r.level, reasons=r.reasons, polyline=r.polyline)


@router.post("/routes/compare", response_model=RouteCompareOut,
             summary="Compara a rota mais rápida com a mais segura, com o motivo do risco")
def compare(data: RouteCompareIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hotspots, reports, cameras = _data(db)
    profile = data.profile or user.profile
    fast, safe = risk_service.compare_routes(
        (data.origin.lat, data.origin.lng), (data.destination.lat, data.destination.lng),
        _local_hour(data.depart_at), profile, hotspots, reports, cameras)
    reduction = 0.0 if fast.score == 0 else round((fast.score - safe.score) / fast.score * 100, 1)
    return RouteCompareOut(fast=_option(fast), safe=_option(safe),
                           time_difference_min=round(safe.duration_min - fast.duration_min, 1),
                           risk_reduction_pct=reduction)


@router.get("/risk/score", response_model=RiskScoreOut, summary="Score de risco de um ponto em um horário")
def risk_score(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
               hour: int = Query(ge=0, le=23), profile: WalkProfile = WalkProfile.default,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hotspots, reports, cameras = _data(db)
    res = risk_service.score_point(lat, lng, hour, profile, hotspots, reports, cameras)
    return RiskScoreOut(lat=lat, lng=lng, hour=hour, score=res.score, level=res.level, reasons=res.reasons)
