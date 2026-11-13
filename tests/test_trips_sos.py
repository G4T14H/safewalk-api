from datetime import timedelta

from app.domain.models import SOSAlert, utcnow
from tests.conftest import CASA, FIAP, make_user


def _accepted_contact(client, auth, name="Mãe"):
    c = client.post("/contacts", json={"name": name, "phone": "+5511999990000"}, headers=auth).json()
    assert c["status"] == "pending"
    accepted = client.post(f"/contacts/accept/{c['invite_token']}").json()
    assert accepted["status"] == "accepted"
    return c["id"]


def _start_trip(client, auth, contact_ids=()):
    return client.post("/trips", json={"origin": FIAP, "destination": CASA, "route_type": "safe",
                                       "contact_ids": list(contact_ids)}, headers=auth)


# ---------- contatos e acompanhamento ----------
def test_pending_contact_cannot_follow(client, auth):
    c = client.post("/contacts", json={"name": "Pai", "phone": "+5511988880000"}, headers=auth).json()
    assert _start_trip(client, auth, [c["id"]]).status_code == 400


def test_invalid_invite_token(client):
    assert client.post("/contacts/accept/nao-existe").status_code == 404


def test_full_trip_flow_with_public_link(client, auth):
    cid = _accepted_contact(client, auth)
    r = _start_trip(client, auth, [cid])
    assert r.status_code == 201
    trip = r.json()
    assert trip["status"] == "active" and len(trip["polyline"]) == 10 and len(trip["shares"]) == 1
    token = trip["shares"][0]["token"]

    client.post(f"/trips/{trip['id']}/locations", json=FIAP, headers=auth)
    track = client.get(f"/public/track/{token}")  # sem autenticação
    assert track.status_code == 200
    assert track.json()["traveler"] == "Ana" and track.json()["last_location"]["lat"] == FIAP["lat"]

    done = client.post(f"/trips/{trip['id']}/complete", headers=auth).json()
    assert done["status"] == "completed"
    assert client.get(f"/public/track/{token}").json()["message"].startswith("Chegou")  # confirmação de chegada
    assert client.post(f"/trips/{trip['id']}/locations", json=FIAP, headers=auth).status_code == 409


def test_link_expires_after_arrival_window(client, auth):
    cid = _accepted_contact(client, auth)
    trip = _start_trip(client, auth, [cid]).json()
    token = trip["shares"][0]["token"]
    client.post(f"/trips/{trip['id']}/complete", headers=auth)
    from app.domain.models import Trip
    with client.session_factory() as s:
        t = s.get(Trip, trip["id"])
        t.ended_at = utcnow() - timedelta(minutes=30)
        s.commit()
    assert client.get(f"/public/track/{token}").status_code == 410
    assert client.get("/public/track/token-falso").status_code == 404


def test_only_one_active_trip_and_ownership(client, auth):
    trip = _start_trip(client, auth).json()
    assert _start_trip(client, auth).status_code == 409
    other = make_user(client, "bia@test.dev", "Bia Lima")
    assert client.get(f"/trips/{trip['id']}", headers=other).status_code == 404
    assert len(client.get("/trips", headers=auth).json()) == 1


# ---------- anomalias ----------
def test_deviation_detected(client, auth):
    trip = _start_trip(client, auth).json()
    far = {"lat": FIAP["lat"] - 0.02, "lng": FIAP["lng"] + 0.02}
    ack = client.post(f"/trips/{trip['id']}/locations", json=far, headers=auth).json()
    assert ack["anomaly"]["trigger"] == "auto_deviation"


def test_unexpected_stop_detected(client, auth):
    trip = _start_trip(client, auth).json()
    p0 = trip["polyline"][0]
    base = utcnow()
    ack = None
    for i in range(4):
        ack = client.post(f"/trips/{trip['id']}/locations",
                          json={"lat": p0[0], "lng": p0[1], "recorded_at": (base + timedelta(seconds=25 * i)).isoformat()},
                          headers=auth).json()
    assert ack["anomaly"]["trigger"] == "auto_stop"


def test_abrupt_motion_detected(client, auth):
    trip = _start_trip(client, auth).json()
    p0, p1 = trip["polyline"][0], trip["polyline"][1]
    base = utcnow()
    client.post(f"/trips/{trip['id']}/locations", json={"lat": p0[0], "lng": p0[1], "recorded_at": base.isoformat()}, headers=auth)
    ack = client.post(f"/trips/{trip['id']}/locations",
                      json={"lat": p1[0], "lng": p1[1], "recorded_at": (base + timedelta(seconds=2)).isoformat()},
                      headers=auth).json()
    assert ack["anomaly"]["trigger"] == "auto_motion"


def test_normal_walk_has_no_anomaly(client, auth):
    trip = _start_trip(client, auth).json()
    p = trip["polyline"][0]
    ack = client.post(f"/trips/{trip['id']}/locations", json={"lat": p[0], "lng": p[1]}, headers=auth).json()
    assert ack["anomaly"] is None


# ---------- SOS ----------
def test_button_sos_notifies_contacts_immediately(client, auth):
    r = client.post("/sos", json={**FIAP, "trigger": "button"}, headers=auth)
    assert r.status_code == 201 and r.json()["status"] == "contacts_notified"


def test_auto_sos_asks_first_then_escalates_by_time(client, auth):
    a = client.post("/sos", json={**FIAP, "trigger": "auto_stop"}, headers=auth).json()
    assert a["status"] == "asking"
    with client.session_factory() as s:  # simula 31 s depois
        s.get(SOSAlert, a["id"]).created_at = utcnow() - timedelta(seconds=31)
        s.commit()
    assert client.get(f"/sos/{a['id']}", headers=auth).json()["status"] == "contacts_notified"
    with client.session_factory() as s:  # simula 3 min depois
        s.get(SOSAlert, a["id"]).created_at = utcnow() - timedelta(seconds=200)
        s.get(SOSAlert, a["id"]).contacts_notified_at = utcnow() - timedelta(seconds=170)
        s.commit()
    final = client.get(f"/sos/{a['id']}", headers=auth).json()
    assert final["status"] == "gcm_notified" and final["gcm_protocol"].startswith("GCM-")
    assert any("GCM" in e["event"] for e in final["timeline"])


def test_manual_escalation_chain(client, auth):
    a = client.post("/sos", json={**FIAP, "trigger": "auto_motion"}, headers=auth).json()
    assert client.post(f"/sos/{a['id']}/escalate", headers=auth).json()["status"] == "contacts_notified"
    assert client.post(f"/sos/{a['id']}/escalate", headers=auth).json()["status"] == "gcm_notified"
    assert client.post(f"/sos/{a['id']}/escalate", headers=auth).status_code == 409


def test_only_correct_pin_cancels(client, auth):
    a = client.post("/sos", json={**FIAP, "trigger": "button"}, headers=auth).json()
    assert client.post(f"/sos/{a['id']}/cancel", json={"pin": "1234"}, headers=auth).status_code == 400  # sem PIN
    client.put("/users/me/pin", json={"pin": "4821"}, headers=auth)
    assert client.post(f"/sos/{a['id']}/cancel", json={"pin": "0000"}, headers=auth).status_code == 403
    ok = client.post(f"/sos/{a['id']}/cancel", json={"pin": "4821"}, headers=auth)
    assert ok.status_code == 200 and ok.json()["status"] == "cancelled"
    assert client.post(f"/sos/{a['id']}/cancel", json={"pin": "4821"}, headers=auth).status_code == 409


def test_sos_isolation_between_users(client, auth):
    a = client.post("/sos", json={**FIAP, "trigger": "button"}, headers=auth).json()
    other = make_user(client, "bia@test.dev", "Bia Lima")
    assert client.get(f"/sos/{a['id']}", headers=other).status_code == 404
    assert client.post("/sos", json={**FIAP, "trip_id": 999}, headers=other).status_code == 404
