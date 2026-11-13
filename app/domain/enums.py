"""Enumerações do domínio SafeWalk."""
import enum


class UserRole(str, enum.Enum):
    citizen = "citizen"
    operator = "operator"  # servidor da Prefeitura / GCM (painel B2G)


class WalkProfile(str, enum.Enum):
    default = "default"
    elderly_pcd = "elderly_pcd"
    child = "child"
    night = "night"


class ContactStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"


class RouteType(str, enum.Enum):
    fast = "fast"
    safe = "safe"


class RiskLevel(str, enum.Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class TripStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class ReportType(str, enum.Enum):
    roubo_celular = "roubo_celular"
    agressao = "agressao"
    assedio = "assedio"
    outro_crime = "outro_crime"
    alagamento = "alagamento"
    calcada_quebrada = "calcada_quebrada"
    rua_sem_luz = "rua_sem_luz"
    obra_calcada = "obra_calcada"


CRIME_TYPES = {ReportType.roubo_celular, ReportType.agressao, ReportType.assedio, ReportType.outro_crime}
INFRA_TYPES = {ReportType.calcada_quebrada, ReportType.rua_sem_luz, ReportType.obra_calcada}


class ReportStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    resolved = "resolved"
    false_report = "false_report"


class SOSTrigger(str, enum.Enum):
    button = "button"
    auto_stop = "auto_stop"
    auto_deviation = "auto_deviation"
    auto_motion = "auto_motion"


class SOSStatus(str, enum.Enum):
    asking = "asking"                      # app perguntou "Tudo bem?"
    contacts_notified = "contacts_notified"
    gcm_notified = "gcm_notified"
    cancelled = "cancelled"


class CameraSource(str, enum.Enum):
    public = "public"
    private = "private"
