"""Detecção de anomalias no trajeto por regras (parada, desvio, movimento brusco)."""
from typing import Optional

from app.services.geo import distance_to_polyline_m, haversine_m

DEVIATION_M = 150.0
STOP_RADIUS_M = 10.0
STOP_SECONDS = 60
ABRUPT_SPEED_M_S = 8.0  # ~29 km/h a pé = corrida/queda/arrancada


def detect(polyline, locations) -> Optional[tuple[str, str]]:
    """Retorna (trigger, mensagem) ou None. `locations` ordenadas por data."""
    if not locations:
        return None
    last = locations[-1]

    if polyline and len(polyline) >= 2:
        d = distance_to_polyline_m((last.lat, last.lng), [tuple(p) for p in polyline])
        if d > DEVIATION_M:
            return "auto_deviation", f"Desvio de {d:.0f} m da rota planejada"

    if len(locations) >= 2:
        prev = locations[-2]
        dt = (last.recorded_at - prev.recorded_at).total_seconds()
        if dt > 0 and haversine_m(prev.lat, prev.lng, last.lat, last.lng) / dt > ABRUPT_SPEED_M_S:
            return "auto_motion", "Movimento brusco detectado"

    window = [p for p in locations if (last.recorded_at - p.recorded_at).total_seconds() <= 120]
    if len(window) >= 3 and (window[-1].recorded_at - window[0].recorded_at).total_seconds() >= STOP_SECONDS:
        if all(haversine_m(p.lat, p.lng, last.lat, last.lng) < STOP_RADIUS_M for p in window):
            return "auto_stop", "Parada inesperada no trajeto"
    return None
