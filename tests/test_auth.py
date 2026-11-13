from tests.conftest import make_user


def test_register_and_login(client):
    r = client.post("/auth/register", json={"name": "Ana Souza", "email": "Ana@Test.dev", "password": "Senha@1234"})
    assert r.status_code == 201
    assert r.json()["email"] == "ana@test.dev" and "password" not in r.json()
    token = client.post("/auth/login", data={"username": "ana@test.dev", "password": "Senha@1234"}).json()
    assert token["token_type"] == "bearer"


def test_duplicate_email_conflict(client):
    make_user(client)
    r = client.post("/auth/register", json={"name": "Outra", "email": "ana@test.dev", "password": "Senha@1234"})
    assert r.status_code == 409


def test_wrong_password_and_invalid_token(client, auth):
    assert client.post("/auth/login", data={"username": "ana@test.dev", "password": "errada123"}).status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert client.get("/users/me").status_code == 401


def test_validation_errors(client):
    r = client.post("/auth/register", json={"name": "A", "email": "nao-e-email", "password": "123"})
    assert r.status_code == 422


def test_profile_and_pin(client, auth):
    assert client.patch("/users/me", json={"profile": "elderly_pcd"}, headers=auth).json()["profile"] == "elderly_pcd"
    assert client.put("/users/me/pin", json={"pin": "12"}, headers=auth).status_code == 422
    assert client.put("/users/me/pin", json={"pin": "4821"}, headers=auth).status_code == 204
    assert client.get("/users/me", headers=auth).json()["has_pin"] is True


def test_rate_limit(client):
    from app.config import settings
    from app.deps import reset_rate_limit
    old = settings.RATE_LIMIT_PER_MINUTE
    settings.RATE_LIMIT_PER_MINUTE = 3
    reset_rate_limit()
    try:
        codes = [client.post("/auth/login", data={"username": "x@x.dev", "password": "12345678"}).status_code
                 for _ in range(5)]
        assert codes[-1] == 429
    finally:
        settings.RATE_LIMIT_PER_MINUTE = old
