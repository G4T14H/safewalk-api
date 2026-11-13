"""Entidades do domínio (SQLAlchemy 2.0). Datas em UTC "naive"."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.enums import (
    CameraSource, ContactStatus, ReportStatus, ReportType, RiskLevel, RouteType,
    SOSStatus, SOSTrigger, TripStatus, UserRole, WalkProfile,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enum_col(e):
    return Enum(e, native_enum=False, length=30, validate_strings=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    pin_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(enum_col(UserRole), default=UserRole.citizen)
    profile: Mapped[WalkProfile] = mapped_column(enum_col(WalkProfile), default=WalkProfile.default)
    reputation: Mapped[float] = mapped_column(Float, default=0.5, server_default="0.5")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    contacts: Mapped[list["TrustedContact"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    trips: Mapped[list["Trip"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def has_pin(self) -> bool:
        return self.pin_hash is not None


class TrustedContact(Base):
    """Contato de confiança. Só vê dados depois de aceitar o convite (consentimento)."""
    __tablename__ = "trusted_contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    status: Mapped[ContactStatus] = mapped_column(enum_col(ContactStatus), default=ContactStatus.pending)
    invite_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="contacts")


class Trip(Base):
    """Trajeto a pé acompanhado."""
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lng: Mapped[float] = mapped_column(Float)
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lng: Mapped[float] = mapped_column(Float)
    route_type: Mapped[RouteType] = mapped_column(enum_col(RouteType))
    route_polyline: Mapped[list] = mapped_column(JSON)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(enum_col(RiskLevel))
    distance_m: Mapped[float] = mapped_column(Float)
    duration_min: Mapped[float] = mapped_column(Float)
    status: Mapped[TripStatus] = mapped_column(enum_col(TripStatus), default=TripStatus.active, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="trips")
    locations: Mapped[list["TripLocation"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripLocation.recorded_at")
    shares: Mapped[list["TripShare"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class TripShare(Base):
    """Link de acompanhamento por contato. Expira quando o trajeto termina."""
    __tablename__ = "trip_shares"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("trusted_contacts.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    trip: Mapped[Trip] = relationship(back_populates="shares")
    contact: Mapped[TrustedContact] = relationship()


class TripLocation(Base):
    __tablename__ = "trip_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    trip: Mapped[Trip] = relationship(back_populates="locations")


class Report(Base):
    """Relato colaborativo. Autor anônimo para o público; peso cresce com confirmações."""
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[ReportType] = mapped_column(enum_col(ReportType), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    details: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)
    anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[float] = mapped_column(Float, default=0.3)
    status: Mapped[ReportStatus] = mapped_column(enum_col(ReportStatus), default=ReportStatus.active, index=True)
    sp156_protocol: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # simulado
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    confirmations: Mapped[list["ReportConfirmation"]] = relationship(back_populates="report", cascade="all, delete-orphan")

    @property
    def confirmation_count(self) -> int:
        return len(self.confirmations)


class ReportConfirmation(Base):
    __tablename__ = "report_confirmations"
    __table_args__ = (UniqueConstraint("report_id", "user_id", name="uq_report_user_confirmation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    report: Mapped[Report] = relationship(back_populates="confirmations")


class Camera(Base):
    """Câmera da rede Smart Sampa (dados de exemplo/mock). Sem imagens nem biometria."""
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    source: Mapped[CameraSource] = mapped_column(enum_col(CameraSource), default=CameraSource.public)


class RiskHotspot(Base):
    """Histórico oficial agregado (SSP-SP, Infosiga, GeoSampa) usado no score de risco."""
    __tablename__ = "risk_hotspots"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[float] = mapped_column(Float, default=200.0)
    base_risk: Mapped[float] = mapped_column(Float)
    lighting_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(60))


class SOSAlert(Base):
    __tablename__ = "sos_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    trip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"), nullable=True)
    trigger: Mapped[SOSTrigger] = mapped_column(enum_col(SOSTrigger))
    status: Mapped[SOSStatus] = mapped_column(enum_col(SOSStatus), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    gcm_protocol: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # simulado
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    contacts_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    gcm_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
