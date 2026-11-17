from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import call_service, get_current_user
from app.domain.models import Trip, User
from app.schemas import AnomalyOut, LocationAck, LocationIn, PublicTrackOut, ShareOut, TripCreate, TripOut
from app.services import trip_service

router = APIRouter(tags=["Trajetos e acompanhamento"])


def _trip_out(trip: Trip) -> TripOut:
    shares = [ShareOut(contact_id=s.contact_id, token=s.token, url=f"/public/track/{s.token}") for s in trip.shares]
    return TripOut(id=trip.id, route_type=trip.route_type, risk_score=trip.risk_score, risk_level=trip.risk_level,
                   distance_m=trip.distance_m, duration_min=trip.duration_min, status=trip.status,
                   started_at=trip.started_at, ended_at=trip.ended_at, polyline=trip.route_polyline, shares=shares)


@router.post("/trips", response_model=TripOut, status_code=201, summary="Inicia um trajeto acompanhado")
def start_trip(data: TripCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = call_service(trip_service.start_trip, db, user, data.origin, data.destination,
                        data.route_type, data.contact_ids)
    return _trip_out(trip)


@router.get("/trips", response_model=list[TripOut], summary="Histórico de trajetos")
def list_trips(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trips = call_service(trip_service.list_trips, db, user.id)
    return [_trip_out(trip) for trip in trips]


@router.get("/trips/{trip_id}", response_model=TripOut, summary="Detalhe de um trajeto")
def get_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = call_service(trip_service.get_owned_trip, db, trip_id, user.id)
    return _trip_out(trip)


@router.post("/trips/{trip_id}/locations", response_model=LocationAck,
             summary="Registra a posição, detecta anomalias e abre um SOS quando necessário")
def add_location(trip_id: int, data: LocationIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    update = call_service(trip_service.add_location, db, trip_id, user.id, data.lat, data.lng, data.recorded_at)
    anomaly = AnomalyOut(trigger=update.anomaly[0], message=update.anomaly[1]) if update.anomaly else None
    return LocationAck(anomaly=anomaly, sos_alert_id=update.sos_alert_id, sos_status=update.sos_status)


@router.post("/trips/{trip_id}/complete", response_model=TripOut,
             summary="Finaliza o trajeto (check-in de chegada) e expira os links")
def complete(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = call_service(trip_service.complete_trip, db, trip_id, user.id)
    return _trip_out(trip)


@router.get("/public/track/{token}", response_model=PublicTrackOut, tags=["Link do contato (público)"],
            summary="Página do contato: localização ao vivo, sem login e sem instalar nada")
def track(token: str, db: Session = Depends(get_db)):
    return call_service(trip_service.public_track, db, token)
