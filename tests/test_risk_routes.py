from app.domain.enums import WalkProfile
from app.domain.models import Camera, RiskHotspot
from app.services import risk_service
from app.services.geo import haversine_m
from tests.conftest import AUGUSTA, CASA, FIAP


def _data(client):
    with client.session_factory() as s:
        return s.query(RiskHotspot).all(), [], s.query(Camera).all()


def test_haversine_known_distance():
    assert 900 < haversine_m(-23.5646, -46.6528, -23.5560, -46.6528) < 1000


def test_night_is_riskier_than_day(client):
    hotspots, reports, cams = _data(client)
    day = risk_service.score_point(AUGUSTA["lat"], AUGUSTA["lng"], 14, WalkProfile.default, hotspots, reports, [])
    night = risk_service.score_point(AUGUSTA["lat"], AUGUSTA["lng"], 23, WalkProfile.default, hotspots, reports, [])
    assert night.score > day.score


def test_cameras_reduce_risk(client):
    hotspots, reports, cams = _data(client)
    without = risk_service.score_point(AUGUSTA["lat"], AUGUSTA["lng"], 23, WalkProfile.default, hotspots, [], [])
    with_cams = risk_service.score_point(AUGUSTA["lat"], AUGUSTA["lng"], 23, WalkProfile.default, hotspots, [], cams)
    assert with_cams.score < without.score
    assert any("câmera" in r for r in with_cams.reasons)


def test_compare_endpoint_safe_never_worse(client, auth):
    body = {"origin": FIAP, "destination": CASA, "depart_at": "2026-11-10T23:00:00"}
    r = client.post("/routes/compare", json=body, headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["safe"]["risk_score"] <= data["fast"]["risk_score"]
    assert data["safe"]["duration_min"] >= data["fast"]["duration_min"] or data["safe"]["polyline"] == data["fast"]["polyline"]
    assert len(data["fast"]["polyline"]) == 10
    assert data["fast"]["risk_level"] in ("low", "moderate", "high")


def test_compare_requires_auth_and_validates(client, auth):
    assert client.post("/routes/compare", json={}).status_code == 401
    bad = {"origin": {"lat": 200, "lng": 0}, "destination": FIAP}
    assert client.post("/routes/compare", json=bad, headers=auth).status_code == 422


def test_risk_score_endpoint(client, auth):
    r = client.get("/risk/score", params={**AUGUSTA, "hour": 23}, headers=auth)
    assert r.status_code == 200 and 0 <= r.json()["score"] <= 1
    assert client.get("/risk/score", params={**AUGUSTA, "hour": 30}, headers=auth).status_code == 422


def test_elderly_profile_penalises_infra(client, auth):
    hotspots, _, _ = _data(client)

    class R:  # relato de calçada quebrada
        lat, lng, weight = FIAP["lat"], FIAP["lng"], 1.0
        type = __import__("app.domain.enums", fromlist=["ReportType"]).ReportType.calcada_quebrada

    base = risk_service.score_point(FIAP["lat"], FIAP["lng"], 14, WalkProfile.default, [], [R], [])
    pcd = risk_service.score_point(FIAP["lat"], FIAP["lng"], 14, WalkProfile.elderly_pcd, [], [R], [])
    assert pcd.score > base.score
