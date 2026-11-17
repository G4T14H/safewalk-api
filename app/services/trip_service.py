"""Application operations for trip lifecycle and anomaly-triggered SOS alerts."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ContactStatus, RouteType, SOSStatus, SOSTrigger, TripStatus
from app.domain.models import Camera, RiskHotspot, SOSAlert, Trip, TripLocation, TripShare, TrustedContact, User, utcnow
from app.security import new_token
from app.services import anomaly_service, report_service, risk_service, sos_service
from app.services.errors import ServiceError
from app.services.timeutil import local_hour

ARRIVAL_VISIBLE = timedelta(minutes=10)


@dataclass
class LocationUpdate:
    anomaly: tuple[str, str] | None = None
    sos_alert_id: int | None = None
    sos_status: SOSStatus | None = None


def _route_inputs(db: Session):
    hotspots = db.scalars(select(RiskHotspot)).all()
    reports = report_service.active_reports(db)
    cameras = db.scalars(select(Camera)).all()
    return hotspots, reports, cameras


def get_owned_trip(db: Session, trip_id: int, user_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if not trip or trip.user_id != user_id:
        raise ServiceError(404, "Trajeto não encontrado")
    return trip


def list_trips(db: Session, user_id: int) -> list[Trip]:
    return db.scalars(select(Trip).where(Trip.user_id == user_id).order_by(Trip.id.desc())).all()


def start_trip(db: Session, user: User, origin, destination, route_type: RouteType,
               contact_ids: list[int]) -> Trip:
    if db.scalar(select(Trip).where(Trip.user_id == user.id, Trip.status == TripStatus.active)):
        raise ServiceError(409, "Já existe um trajeto ativo. Finalize-o antes de iniciar outro.")

    contacts = []
    for contact_id in contact_ids:
        contact = db.get(TrustedContact, contact_id)
        if not contact or contact.user_id != user.id:
            raise ServiceError(404, f"Contato {contact_id} não encontrado")
        if contact.status != ContactStatus.accepted:
            raise ServiceError(400, f"Contato {contact_id} ainda não aceitou o convite")
        contacts.append(contact)

    hotspots, reports, cameras = _route_inputs(db)
    fast, safe = risk_service.compare_routes(
        (origin.lat, origin.lng), (destination.lat, destination.lng),
        local_hour(None), user.profile, hotspots, reports, cameras)
    chosen = safe if route_type == RouteType.safe else fast
    trip = Trip(user_id=user.id, origin_lat=origin.lat, origin_lng=origin.lng,
                dest_lat=destination.lat, dest_lng=destination.lng, route_type=route_type,
                route_polyline=[list(point) for point in chosen.polyline], risk_score=chosen.score,
                risk_level=chosen.level, distance_m=chosen.distance_m, duration_min=chosen.duration_min)
    trip.shares = [TripShare(contact_id=contact.id, token=new_token()) for contact in contacts]
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def add_location(db: Session, trip_id: int, user_id: int, lat: float, lng: float,
                 recorded_at: datetime | None) -> LocationUpdate:
    trip = get_owned_trip(db, trip_id, user_id)
    if trip.status != TripStatus.active:
        raise ServiceError(409, "Trajeto não está ativo")

    db.add(TripLocation(trip_id=trip.id, lat=lat, lng=lng, recorded_at=recorded_at or utcnow()))
    db.commit()
    db.refresh(trip)
    anomaly = anomaly_service.detect(trip.route_polyline, trip.locations)
    if not anomaly:
        return LocationUpdate()

    # Avoid creating a new alert for every subsequent location while this trip's SOS is active.
    alert = db.scalar(select(SOSAlert).where(
        SOSAlert.trip_id == trip.id, SOSAlert.status != SOSStatus.cancelled).order_by(SOSAlert.id.desc()))
    if alert is None:
        alert = sos_service.start(user_id, trip.id, SOSTrigger(anomaly[0]), lat, lng)
        db.add(alert)
        db.commit()
        db.refresh(alert)
    return LocationUpdate(anomaly=anomaly, sos_alert_id=alert.id, sos_status=alert.status)


def complete_trip(db: Session, trip_id: int, user_id: int) -> Trip:
    trip = get_owned_trip(db, trip_id, user_id)
    if trip.status != TripStatus.active:
        raise ServiceError(409, "Trajeto não está ativo")
    trip.status = TripStatus.completed
    trip.ended_at = utcnow()
    db.commit()
    db.refresh(trip)
    return trip


def public_track(db: Session, token: str) -> dict:
    share = db.scalar(select(TripShare).where(TripShare.token == token))
    if not share or share.contact.status != ContactStatus.accepted:
        raise ServiceError(404, "Link inválido")
    trip = share.trip
    arrived_recently = (trip.status == TripStatus.completed and trip.ended_at
                        and utcnow() - trip.ended_at <= ARRIVAL_VISIBLE)
    if trip.status != TripStatus.active and not arrived_recently:
        raise ServiceError(410, "Este link expirou: o trajeto terminou")
    last = trip.locations[-1] if trip.locations else None
    return {
        "traveler": trip.user.name.split()[0],
        "status": trip.status,
        "risk_level": trip.risk_level,
        "started_at": trip.started_at,
        "last_location": {"lat": last.lat, "lng": last.lng} if last else None,
        "polyline": [tuple(point) for point in trip.route_polyline],
        "message": "Chegou ao destino em segurança" if trip.status == TripStatus.completed else "A caminho",
    }
