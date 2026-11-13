import os
import tempfile

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from tests.conftest import AUGUSTA, FIAP


def test_dashboard_is_operator_only(client, auth, operator):
    assert client.get("/dashboard/overview", headers=auth).status_code == 403
    assert client.get("/dashboard/overview").status_code == 401
    assert client.get("/dashboard/overview", headers=operator).status_code == 200


def test_dashboard_aggregates(client, auth, operator):
    client.post("/reports", json={**AUGUSTA, "type": "roubo_celular"}, headers=auth)
    client.post("/reports", json={**FIAP, "type": "rua_sem_luz"}, headers=auth)
    client.post("/sos", json={**FIAP, "trigger": "button"}, headers=auth)
    d = client.get("/dashboard/overview", headers=operator).json()
    assert d["reports_received"] == 2 and d["sos_confirmed"] == 1 and d["sp156_open"] == 1
    assert d["cameras_registered"] >= 1 and len(d["critical_points"]) == 2


def test_cameras(client, auth, operator):
    near = client.get("/cameras", params={**FIAP, "radius_m": 300}, headers=auth).json()
    assert near and "image" not in near[0]
    new = {"name": "Câmera nova", **AUGUSTA, "source": "private"}
    assert client.post("/cameras", json=new, headers=auth).status_code == 403
    assert client.post("/cameras", json=new, headers=operator).status_code == 201


def test_health_and_openapi(client):
    assert client.get("/health").json()["status"] == "ok"
    spec = client.get("/openapi.json").json()
    assert {"/routes/compare", "/sos", "/reports", "/trips", "/public/track/{token}"} <= set(spec["paths"])
    assert client.get("/docs").status_code == 200


def _columns(url, table):
    engine = create_engine(url)
    try:
        return [c["name"] for c in inspect(engine).get_columns(table)]
    finally:
        engine.dispose()  # libera o arquivo (o Windows não apaga SQLite aberto)


def _tables(url):
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_alembic_migrations_upgrade_and_downgrade():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        url = f"sqlite:///{os.path.join(tmp, 'mig.db')}"
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        assert {"users", "trusted_contacts", "trips", "trip_shares", "trip_locations", "reports",
                "report_confirmations", "cameras", "risk_hotspots", "sos_alerts"} <= _tables(url)
        assert "reputation" in _columns(url, "users")
        command.downgrade(cfg, "0001")
        assert "reputation" not in _columns(url, "users")
