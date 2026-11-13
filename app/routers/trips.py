from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain.enums import ContactStatus, RouteType, TripStatus
from app.domain.models import TrustedContact, Trip, TripLocation, TripShare, User, utcnow
from app.routers.routes import _data, _local_hour
from app.schemas import (AnomalyOut, Coord, LocationAck, LocationIn, PublicTrackOut, ShareOut, TripCreate, TripOut)
from app.security import new_token
from app.services import anomaly_service, risk_service

router = APIRouter(tags=["Trajetos e acompanhamento"])
ARRIVAL_VISIBLE = timedelta(minutes=10)


def _trip_out(trip: Trip) -> TripOut:
    shares = [ShareOut(contact_id=s.contact_id, token=s.token, url=f"/public/track/{s.token}") for s in trip.shares]
    return TripOut(id=trip.id, route_type=trip.route_type, risk_score=trip.risk_score, risk_level=trip.risk_level,
                   distance_m=trip.distance_m, duration_min=trip.duration_min, status=trip.status,
                   started_at=trip.started_at, ended_at=trip.ended_at, polyline=trip.route_polyline, shares=shares)


def _own_trip(db: Session, trip_id: int, user: User) -> Trip:
    trip = db.get(Trip, trip_id)
    if not trip or trip.user_id != user.id:
        raise HTTPException(404, "Trajeto não encontrado")
    return trip


@router.post("/trips", response_model=TripOut, status_code=201, summary="Inicia um trajeto acompanhado")
def start_trip(data: TripCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.scalar(select(Trip).where(Trip.user_id == user.id, Trip.status == TripStatus.active)):
        raise HTTPException(409, "Já existe um trajeto ativo. Finalize-o antes de iniciar outro.")
    contacts = []
    for cid in data.contact_ids:
        c = db.get(TrustedContact, cid)
        if not c or c.user_id != user.id:
            raise HTTPException(404, f"Contato {cid} não encontrado")
        if c.status != ContactStatus.accepted:
            raise HTTPException(400, f"Contato {cid} ainda não aceitou o convite")
        contacts.append(c)

    hotspots, reports, cameras = _data(db)
    fast, safe = risk_service.compare_routes(
        (data.origin.lat, data.origin.lng), (data.destination.lat, data.destination.lng),
        _local_hour(None), user.profile, hotspots, reports, cameras)
    chosen = safe if data.route_type == RouteType.safe else fast

    trip = Trip(user_id=user.id, origin_lat=data.origin.lat, origin_lng=data.origin.lng,
                dest_lat=data.destination.lat, dest_lng=data.destination.lng, route_type=data.route_type,
                route_polyline=[list(p) for p in chosen.polyline], risk_score=chosen.score,
                risk_level=chosen.level, distance_m=chosen.distance_m, duration_min=chosen.duration_min)
    trip.shares = [TripShare(contact_id=c.id, token=new_token()) for c in contacts]
    db.add(trip)
    db.commit()
    return _trip_out(trip)


@router.get("/trips", response_model=list[TripOut], summary="Histórico de trajetos")
def list_trips(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trips = db.scalars(select(Trip).where(Trip.user_id == user.id).order_by(Trip.id.desc())).all()
    return [_trip_out(t) for t in trips]


@router.get("/trips/{trip_id}", response_model=TripOut, summary="Detalhe de um trajeto")
def get_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _trip_out(_own_trip(db, trip_id, user))


@router.post("/trips/{trip_id}/locations", response_model=LocationAck,
             summary="Registra a posição e detecta parada, desvio ou movimento brusco")
def add_location(trip_id: int, data: LocationIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    trip = _own_trip(db, trip_id, user)
    if trip.status != TripStatus.active:
        raise HTTPException(409, "Trajeto não está ativo")
    db.add(TripLocation(trip_id=trip.id, lat=data.lat, lng=data.lng, recorded_at=data.recorded_at or utcnow()))
    db.commit()
    db.refresh(trip)
    found = anomaly_service.detect(trip.route_polyline, trip.locations)
    return LocationAck(anomaly=AnomalyOut(trigger=found[0], message=found[1]) if found else None)


@router.post("/trips/{trip_id}/complete", response_model=TripOut,
             summary="Finaliza o trajeto (check-in de chegada) e expira os links")
def complete(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = _own_trip(db, trip_id, user)
    if trip.status != TripStatus.active:
        raise HTTPException(409, "Trajeto não está ativo")
    trip.status = TripStatus.completed
    trip.ended_at = utcnow()
    db.commit()
    return _trip_out(trip)


@router.get("/public/track/{token}", response_model=PublicTrackOut, tags=["Link do contato (público)"],
            summary="Página do contato: localização ao vivo, sem login e sem instalar nada")
def track(token: str, db: Session = Depends(get_db)):
    share = db.scalar(select(TripShare).where(TripShare.token == token))
    if not share or share.contact.status != ContactStatus.accepted:
        raise HTTPException(404, "Link inválido")
    trip = share.trip
    arrived_recently = (trip.status == TripStatus.completed and trip.ended_at
                        and utcnow() - trip.ended_at <= ARRIVAL_VISIBLE)
    if trip.status != TripStatus.active and not arrived_recently:
        raise HTTPException(410, "Este link expirou: o trajeto terminou")
    last = trip.locations[-1] if trip.locations else None
    message = "Chegou ao destino em segurança" if trip.status == TripStatus.completed else "A caminho"
    return PublicTrackOut(
        traveler=trip.user.name.split()[0], status=trip.status, risk_level=trip.risk_level,
        started_at=trip.started_at, last_location=Coord(lat=last.lat, lng=last.lng) if last else None,
        polyline=[tuple(p) for p in trip.route_polyline], message=message)
