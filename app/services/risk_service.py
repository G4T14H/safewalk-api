"""Score de risco por ponto/horário e comparação rota rápida vs. segura.

Score 0..1 = histórico oficial (hotspots) x fator de horário
           + relatos colaborativos ativos (peso progressivo)
           + penalidade de iluminação - redução por câmeras próximas.
Perfis (idoso/PCD, criança, noite) alteram o peso de cada risco.
"""
from dataclasses import dataclass, field
from math import pi, sin, sqrt

from app.domain.enums import CRIME_TYPES, INFRA_TYPES, ReportType, RiskLevel, WalkProfile
from app.services.geo import Point, haversine_m, polyline_length_m

WALK_SPEED_M_PER_MIN = 80.0
REPORT_RADIUS_M = 150.0
CAMERA_RADIUS_M = 100.0

TYPE_WEIGHT = {
    ReportType.roubo_celular: 1.0, ReportType.agressao: 1.0, ReportType.assedio: 0.9,
    ReportType.outro_crime: 0.8, ReportType.alagamento: 0.9, ReportType.calcada_quebrada: 0.35,
    ReportType.rua_sem_luz: 0.5, ReportType.obra_calcada: 0.3,
}
TYPE_LABEL = {
    ReportType.roubo_celular: "Roubo de celular relatado", ReportType.agressao: "Agressão relatada",
    ReportType.assedio: "Assédio relatado", ReportType.outro_crime: "Ocorrência criminal relatada",
    ReportType.alagamento: "Alagamento ativo", ReportType.calcada_quebrada: "Calçada quebrada",
    ReportType.rua_sem_luz: "Rua sem iluminação", ReportType.obra_calcada: "Obra na calçada",
}


def hour_factor(hour: int, profile: WalkProfile = WalkProfile.default) -> float:
    if hour >= 22 or hour < 5:
        f = 1.0
    elif 18 <= hour < 22:
        f = 0.75
    elif 5 <= hour < 7:
        f = 0.5
    else:
        f = 0.3
    return max(f, 0.75) if profile == WalkProfile.night else f


def level_for(score: float) -> RiskLevel:
    if score < 0.35:
        return RiskLevel.low
    if score < 0.65:
        return RiskLevel.moderate
    return RiskLevel.high


@dataclass
class ScoreResult:
    score: float
    reasons: list[str] = field(default_factory=list)

    @property
    def level(self) -> RiskLevel:
        return level_for(self.score)


def score_point(lat, lng, hour, profile, hotspots, reports, cameras) -> ScoreResult:
    factor = hour_factor(hour, profile)
    reasons: list[str] = []

    hist, lighting = 0.0, 0.0
    for h in hotspots:
        d = haversine_m(lat, lng, h.lat, h.lng)
        if d < h.radius_m:
            hist += h.base_risk * (1 - d / h.radius_m)
            if not h.lighting_ok:
                lighting = max(lighting, 0.15)
    hist = min(hist, 1.0) * factor
    if hist >= 0.2:
        reasons.append("Histórico de ocorrências nesta região e horário")
    if lighting:
        reasons.append("Iluminação fraca")

    dynamic = 0.0
    for r in reports:
        d = haversine_m(lat, lng, r.lat, r.lng)
        if d > REPORT_RADIUS_M:
            continue
        w = r.weight * TYPE_WEIGHT[r.type] * (1 - 0.5 * d / REPORT_RADIUS_M)
        if r.type in CRIME_TYPES:
            w *= max(factor, 0.4)
        if r.type in INFRA_TYPES and profile == WalkProfile.elderly_pcd:
            w *= 1.5
        dynamic += w
        label = TYPE_LABEL[r.type]
        if label not in reasons:
            reasons.append(label)

    n_cams = sum(1 for c in cameras if haversine_m(lat, lng, c.lat, c.lng) <= CAMERA_RADIUS_M)
    reduction = min(0.3, 0.1 * n_cams)
    if n_cams:
        reasons.append(f"{n_cams} câmera(s) monitorando o trecho")

    score = hist + lighting + 0.6 * dynamic - reduction
    if profile == WalkProfile.child:
        score *= 1.2
    return ScoreResult(round(max(0.0, min(1.0, score)), 3), reasons)


def build_polyline(origin: Point, dest: Point, offset: float, n: int = 10) -> list[Point]:
    dlat, dlng = dest[0] - origin[0], dest[1] - origin[1]
    norm = sqrt(dlat ** 2 + dlng ** 2) or 1.0
    perp = (-dlng / norm, dlat / norm)
    pts = []
    for i in range(n):
        t = i / (n - 1)
        bump = offset * sin(pi * t)
        pts.append((round(origin[0] + dlat * t + perp[0] * bump, 6), round(origin[1] + dlng * t + perp[1] * bump, 6)))
    return pts


@dataclass
class RouteResult:
    kind: str
    polyline: list[Point]
    distance_m: float
    duration_min: float
    score: float
    reasons: list[str]

    @property
    def level(self) -> RiskLevel:
        return level_for(self.score)


def evaluate_route(kind, polyline, hour, profile, hotspots, reports, cameras) -> RouteResult:
    results = [score_point(p[0], p[1], hour, profile, hotspots, reports, cameras) for p in polyline]
    scores = [r.score for r in results]
    route_score = round(0.6 * (sum(scores) / len(scores)) + 0.4 * max(scores), 3)
    reasons: list[str] = []
    for r in results:
        for reason in r.reasons:
            if reason not in reasons:
                reasons.append(reason)
    dist = polyline_length_m(polyline)
    return RouteResult(kind, polyline, round(dist, 1), round(dist / WALK_SPEED_M_PER_MIN, 1), route_score, reasons[:5])


CANDIDATE_OFFSETS = (0.0, 0.0015, -0.0015, 0.003, -0.003)  # ~165 m e ~330 m de desvio lateral
MAX_DETOUR_FACTOR = 1.6


def compare_routes(origin: Point, dest: Point, hour, profile, hotspots, reports, cameras):
    """Retorna (rota_rapida, rota_segura). A rápida é a linha reta; a segura é o
    candidato de menor risco cujo tempo não passa de 1,6x o da rápida."""
    candidates = [
        evaluate_route("fast" if off == 0 else "candidate", build_polyline(origin, dest, off),
                       hour, profile, hotspots, reports, cameras)
        for off in CANDIDATE_OFFSETS
    ]
    fast = candidates[0]
    viable = [c for c in candidates if c.duration_min <= fast.duration_min * MAX_DETOUR_FACTOR]
    best = min(viable, key=lambda c: (c.score, c.duration_min))
    safe = RouteResult("safe", best.polyline, best.distance_m, best.duration_min, best.score, best.reasons)
    return fast, safe
