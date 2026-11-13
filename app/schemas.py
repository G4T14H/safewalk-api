"""Contratos de entrada/saída da API (Pydantic v2)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.timeutil import to_naive_utc
from app.domain.enums import (
    CameraSource, ContactStatus, ReportStatus, ReportType, RiskLevel, RouteType,
    SOSStatus, SOSTrigger, TripStatus, UserRole, WalkProfile,
)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Coord(BaseModel):
    lat: float = Field(ge=-90, le=90, examples=[-23.5646])
    lng: float = Field(ge=-180, le=180, examples=[-46.6528])


# ---------- Auth / usuário ----------
class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    profile: Optional[WalkProfile] = None


class PinSet(BaseModel):
    pin: str = Field(pattern=r"^\d{4,6}$", examples=["4821"])


class UserOut(ORM):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    profile: WalkProfile
    has_pin: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Contatos ----------
class ContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=30, examples=["+5511999990000"])


class ContactOut(ORM):
    id: int
    name: str
    phone: str
    status: ContactStatus
    invite_token: str
    created_at: datetime
    accepted_at: Optional[datetime]


# ---------- Rotas / risco ----------
class RouteCompareIn(BaseModel):
    origin: Coord
    destination: Coord
    depart_at: Optional[datetime] = Field(default=None, description="Com fuso (ex.: Z) é convertido para o horário de São Paulo; sem fuso é lido como horário local. Padrão: agora.")
    profile: Optional[WalkProfile] = Field(default=None, description="Padrão: perfil do usuário")


class RouteOption(BaseModel):
    kind: str
    distance_m: float
    duration_min: float
    risk_score: float
    risk_level: RiskLevel
    reasons: list[str]
    polyline: list[tuple[float, float]]


class RouteCompareOut(BaseModel):
    fast: RouteOption
    safe: RouteOption
    time_difference_min: float
    risk_reduction_pct: float


class RiskScoreOut(BaseModel):
    lat: float
    lng: float
    hour: int
    score: float
    level: RiskLevel
    reasons: list[str]


# ---------- Trajetos ----------
class TripCreate(BaseModel):
    origin: Coord
    destination: Coord
    route_type: RouteType = RouteType.safe
    contact_ids: list[int] = Field(default_factory=list, description="Contatos (já aceitos) que acompanharão")


class ShareOut(BaseModel):
    contact_id: int
    token: str
    url: str


class TripOut(BaseModel):
    id: int
    route_type: RouteType
    risk_score: float
    risk_level: RiskLevel
    distance_m: float
    duration_min: float
    status: TripStatus
    started_at: datetime
    ended_at: Optional[datetime]
    polyline: list[tuple[float, float]]
    shares: list[ShareOut] = []


class LocationIn(Coord):
    recorded_at: Optional[datetime] = Field(
        default=None, description="Aceita fuso (ex.: -03:00 ou Z); é convertido para UTC. Padrão: agora.")

    @field_validator("recorded_at")
    @classmethod
    def _to_utc(cls, v):
        return to_naive_utc(v)


class AnomalyOut(BaseModel):
    trigger: SOSTrigger
    message: str


class LocationAck(BaseModel):
    recorded: bool = True
    anomaly: Optional[AnomalyOut] = None


class PublicTrackOut(BaseModel):
    traveler: str
    status: TripStatus
    risk_level: RiskLevel
    started_at: datetime
    last_location: Optional[Coord]
    polyline: list[tuple[float, float]]
    message: str


# ---------- Relatos ----------
class ReportCreate(Coord):
    type: ReportType
    details: Optional[str] = Field(default=None, max_length=280)
    anonymous: bool = True


class ReportOut(ORM):
    id: int
    type: ReportType
    lat: float
    lng: float
    details: Optional[str]
    weight: float
    confirmation_count: int
    status: ReportStatus
    sp156_protocol: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]


class ReportResolve(BaseModel):
    status: ReportStatus = Field(description="resolved ou false_report")


# ---------- SOS ----------
class SOSCreate(Coord):
    trip_id: Optional[int] = None
    trigger: SOSTrigger = SOSTrigger.button


class SOSCancel(BaseModel):
    pin: str = Field(pattern=r"^\d{4,6}$")


class TimelineItem(BaseModel):
    event: str
    at: datetime


class SOSOut(BaseModel):
    id: int
    status: SOSStatus
    trigger: SOSTrigger
    lat: float
    lng: float
    gcm_protocol: Optional[str]
    created_at: datetime
    timeline: list[TimelineItem]


# ---------- Câmeras / painel ----------
class CameraCreate(Coord):
    name: str = Field(min_length=2, max_length=120)
    source: CameraSource = CameraSource.public


class CameraOut(ORM):
    id: int
    name: str
    lat: float
    lng: float
    source: CameraSource


class CriticalPoint(BaseModel):
    lat: float
    lng: float
    reports: int
    predominant_type: ReportType


class DashboardOut(BaseModel):
    period_days: int
    reports_received: int
    sos_confirmed: int
    sp156_open: int
    cameras_registered: int
    critical_points: list[CriticalPoint]
