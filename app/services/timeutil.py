"""Tratamento de datas/fusos. O banco guarda UTC "naive"; São Paulo é UTC-3 (sem horário de verão desde 2019)."""
from datetime import datetime, timedelta, timezone
from typing import Optional

BRT = timezone(timedelta(hours=-3))


def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Converte datas com fuso para UTC sem fuso. Datas sem fuso são tratadas como já estando em UTC."""
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def local_hour(dt: Optional[datetime] = None) -> int:
    """Hora local de São Paulo. Sem argumento = agora. Data sem fuso = já é horário local."""
    if dt is None:
        return datetime.now(BRT).hour
    if dt.tzinfo is None:
        return dt.hour
    return dt.astimezone(BRT).hour
