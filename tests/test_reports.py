from datetime import timedelta

from app.domain.models import Report, utcnow
from tests.conftest import AUGUSTA, FIAP, make_user

REPORT = {**AUGUSTA, "type": "roubo_celular", "details": "dois homens de moto"}


def test_create_report_is_anonymous_and_low_weight(client, auth):
    r = client.post("/reports", json=REPORT, headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert "author_id" not in body and body["weight"] < 0.5 and body["confirmation_count"] == 0
    assert body["expires_at"] is not None and body["sp156_protocol"] is None


def test_infra_report_gets_sp156_protocol_and_no_expiry(client, auth):
    body = client.post("/reports", json={**FIAP, "type": "calcada_quebrada"}, headers=auth).json()
    assert body["sp156_protocol"].startswith("SP156-") and body["expires_at"] is None


def test_confirmation_raises_weight_and_blocks_abuse(client, auth):
    rid = client.post("/reports", json=REPORT, headers=auth).json()["id"]
    other = make_user(client, "bia@test.dev", "Bia Lima")
    r = client.post(f"/reports/{rid}/confirm", headers=other)
    assert r.status_code == 200 and r.json()["confirmation_count"] == 1
    assert r.json()["weight"] > 0.3
    assert client.post(f"/reports/{rid}/confirm", headers=other).status_code == 409   # já confirmou
    assert client.post(f"/reports/{rid}/confirm", headers=auth).status_code == 400    # próprio relato


def test_duplicate_report_rejected(client, auth):
    assert client.post("/reports", json=REPORT, headers=auth).status_code == 201
    assert client.post("/reports", json=REPORT, headers=auth).status_code == 409


def test_spam_limit(client, auth):
    for i in range(5):
        r = client.post("/reports", json={"lat": -23.50 - i * 0.01, "lng": -46.60, "type": "outro_crime"}, headers=auth)
        assert r.status_code == 201
    assert client.post("/reports", json={"lat": -23.9, "lng": -46.6, "type": "assedio"}, headers=auth).status_code == 429


def test_nearby_and_expiry(client, auth):
    rid = client.post("/reports", json=REPORT, headers=auth).json()["id"]
    assert len(client.get("/reports", params={**AUGUSTA, "radius_m": 500}, headers=auth).json()) == 1
    assert client.get("/reports", params={**FIAP, "radius_m": 100}, headers=auth).json() == []
    with client.session_factory() as s:  # envelhece o relato: expira
        rep = s.get(Report, rid)
        rep.expires_at = utcnow() - timedelta(minutes=1)
        s.commit()
    assert client.get("/reports", params={**AUGUSTA, "radius_m": 500}, headers=auth).json() == []


def test_report_raises_route_risk(client, auth):
    before = client.get("/risk/score", params={**FIAP, "hour": 23}, headers=auth).json()["score"]
    other = make_user(client, "bia@test.dev", "Bia Lima")
    rid = client.post("/reports", json={**FIAP, "type": "assedio"}, headers=auth).json()["id"]
    client.post(f"/reports/{rid}/confirm", headers=other)
    after = client.get("/risk/score", params={**FIAP, "hour": 23}, headers=auth).json()
    assert after["score"] > before and "Assédio relatado" in after["reasons"]


def test_operator_resolves_and_flags_false(client, auth, operator):
    rid = client.post("/reports", json=REPORT, headers=auth).json()["id"]
    assert client.patch(f"/reports/{rid}/resolve", json={"status": "resolved"}, headers=auth).status_code == 403
    r = client.patch(f"/reports/{rid}/resolve", json={"status": "false_report"}, headers=operator)
    assert r.json()["status"] == "false_report"
    assert client.patch(f"/reports/{rid}/resolve", json={"status": "active"}, headers=operator).status_code == 422


def test_author_can_delete_only_own(client, auth):
    rid = client.post("/reports", json=REPORT, headers=auth).json()["id"]
    other = make_user(client, "bia@test.dev", "Bia Lima")
    assert client.delete(f"/reports/{rid}", headers=other).status_code == 404
    assert client.delete(f"/reports/{rid}", headers=auth).status_code == 204
