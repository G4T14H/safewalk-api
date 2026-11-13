import os

os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.domain.models  # noqa: F401
from app.database import Base, get_db
from app.deps import reset_rate_limit
from app.domain.enums import UserRole
from app.domain.models import User
from app.main import app
from app.seed import CAMERAS, HOTSPOTS
from app.domain.models import Camera, RiskHotspot
from app.security import hash_secret

# Pontos de teste (região Bela Vista/Consolação)
FIAP = {"lat": -23.5646, "lng": -46.6528}
CASA = {"lat": -23.5530, "lng": -46.6525}
AUGUSTA = {"lat": -23.5560, "lng": -46.6600}


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        s.add_all(RiskHotspot(name=n, lat=la, lng=ln, radius_m=r, base_risk=b, lighting_ok=li, source=src)
                  for n, la, ln, r, b, li, src in HOTSPOTS)
        s.add_all(Camera(name=n, lat=la, lng=ln, source=src) for n, la, ln, src in CAMERAS)
        s.add(User(name="Operador", email="op@test.dev", password_hash=hash_secret("Operador@123"),
                   role=UserRole.operator))
        s.commit()
    yield Session
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def override():
        db = db_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    reset_rate_limit()
    with TestClient(app) as c:
        c.session_factory = db_session
        yield c
    app.dependency_overrides.clear()


def make_user(client, email="ana@test.dev", name="Ana Souza", password="Senha@1234"):
    client.post("/auth/register", json={"name": name, "email": email, "password": password})
    r = client.post("/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def auth(client):
    return make_user(client)


@pytest.fixture()
def operator(client):
    r = client.post("/auth/login", data={"username": "op@test.dev", "password": "Operador@123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
