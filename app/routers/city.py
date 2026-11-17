"""HTTP endpoints for mock camera data and the municipal dashboard."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import call_service, get_current_user, require_operator
from app.schemas import CameraCreate, CameraOut, DashboardOut
from app.services import city_service

router = APIRouter(tags=["Prefeitura / Smart Sampa"])


@router.get("/cameras", response_model=list[CameraOut], summary="Câmeras num raio (só posição; sem imagem)")
def cameras(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
            radius_m: float = Query(1000, gt=0, le=10000), user=Depends(get_current_user),
            db: Session = Depends(get_db)):
    return call_service(city_service.cameras_near, db, lat, lng, radius_m)


@router.post("/cameras", response_model=CameraOut, status_code=201, summary="Cadastra câmera (operador)")
def add_camera(data: CameraCreate, op=Depends(require_operator), db: Session = Depends(get_db)):
    return call_service(city_service.add_camera, db, data)


@router.get("/dashboard/overview", response_model=DashboardOut,
            summary="Painel da Prefeitura: relatos, SOS, chamados SP156 e pontos críticos")
def overview(days: int = Query(7, ge=1, le=90), op=Depends(require_operator), db: Session = Depends(get_db)):
    return call_service(city_service.dashboard_overview, db, days)
