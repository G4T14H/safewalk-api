from datetime import datetime, timezone

from sqlalchemy import select

from app.domain.models import TripLocation
from app.services.timeutil import local_hour, to_naive_utc
from tests.conftest import CASA, FIAP, make_user


def test_to_naive_utc_and_local_hour():
    aware = datetime(2026, 11, 11, 23, 0, tzinfo=timezone.utc)
    assert to_naive_utc(aware) == datetime(2026, 11, 11, 23, 0) and to_naive_utc(aware).tzinfo is None
    assert local_hour(aware) == 20                       # 23:00Z = 20h em São Paulo
    assert local_hour(datetime(2026, 11, 11, 20, 0)) == 20  # sem fuso = já é horário local
    assert 0 <= local_hour() <= 23


def test_location_with_offset_is_stored_as_utc(client, auth):
    trip = client.post("/trips", json={"origin": FIAP, "destination": CASA}, headers=auth).json()
    client.post(f"/trips/{trip['id']}/locations", json={**FIAP, "recorded_at": "2026-11-11T23:00:00-03:00"}, headers=auth)
    client.post(f"/trips/{trip['id']}/locations", json={**FIAP, "recorded_at": "2026-11-12T02:00:00Z"}, headers=auth)
    with client.session_factory() as s:
        times = [l.recorded_at for l in s.scalars(select(TripLocation))]
    assert times == [datetime(2026, 11, 12, 2, 0), datetime(2026, 11, 12, 2, 0)]


def test_compare_converts_depart_at_timezone(client, auth):
    body = {"origin": {"lat": -23.5560, "lng": -46.6600}, "destination": FIAP}
    z = client.post("/routes/compare", json={**body, "depart_at": "2026-11-11T02:00:00Z"}, headers=auth).json()   # 23h em SP
    local = client.post("/routes/compare", json={**body, "depart_at": "2026-11-10T23:00:00"}, headers=auth).json()
    day = client.post("/routes/compare", json={**body, "depart_at": "2026-11-10T14:00:00"}, headers=auth).json()
    assert z["fast"]["risk_score"] == local["fast"]["risk_score"] > day["fast"]["risk_score"]


def test_same_origin_and_destination(client, auth):
    r = client.post("/routes/compare", json={"origin": FIAP, "destination": FIAP}, headers=auth)
    assert r.status_code == 200 and r.json()["fast"]["distance_m"] == 0


def test_contacts_delete_and_ownership(client, auth):
    c = client.post("/contacts", json={"name": "Pai", "phone": "+5511988880000"}, headers=auth).json()
    other = make_user(client, "bia@test.dev", "Bia Lima")
    assert client.delete(f"/contacts/{c['id']}", headers=other).status_code == 404
    assert client.delete(f"/contacts/{c['id']}", headers=auth).status_code == 204
    assert client.get("/contacts", headers=auth).json() == []


def test_list_sos_alerts(client, auth):
    client.post("/sos", json={**FIAP, "trigger": "button"}, headers=auth)
    client.post("/sos", json={**FIAP, "trigger": "auto_stop"}, headers=auth)
    alerts = client.get("/sos", headers=auth).json()
    assert [a["trigger"] for a in alerts] == ["auto_stop", "button"]   # mais recente primeiro
