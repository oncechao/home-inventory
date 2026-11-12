from sqlalchemy import select

from app.models import User
from helpers import PASSWORD, register


def test_register_logs_user_in(client):
    user = register(client, "alice")
    assert user["username"] == "alice"
    assert client.get("/api/auth/me").json()["username"] == "alice"


def test_register_rejects_duplicate_username(client, new_client):
    register(client, "alice")
    r = new_client().post("/api/auth/register", json={"username": "alice", "password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["detail"] == "用户名已被占用"


def test_register_validates_input(client):
    assert client.post("/api/auth/register", json={"username": "bob", "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "a b", "password": PASSWORD}).status_code == 422
    assert client.post("/api/auth/register", json={"username": "张三丰", "password": PASSWORD}).status_code == 201


def test_password_is_hashed(app, client):
    register(client, "alice")
    with app.state.SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("$argon2")


def test_me_requires_login(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "请先登录"


def test_login_and_logout(client, new_client):
    register(client, "alice")
    other = new_client()
    assert other.post("/api/auth/login", json={"username": "alice", "password": "wrong-pass"}).status_code == 401
    assert other.post("/api/auth/login", json={"username": "nobody", "password": PASSWORD}).status_code == 401
    assert other.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 200
    assert other.get("/api/auth/me").status_code == 200
    assert other.post("/api/auth/logout").status_code == 204
    assert other.get("/api/auth/me").status_code == 401


def test_change_password(client, new_client):
    register(client, "alice")
    bad = client.post("/api/auth/password", json={"old_password": "nope", "new_password": "newpassword1"})
    assert bad.status_code == 400
    ok = client.post("/api/auth/password", json={"old_password": PASSWORD, "new_password": "newpassword1"})
    assert ok.status_code == 204
    other = new_client()
    assert other.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 401
    assert other.post("/api/auth/login", json={"username": "alice", "password": "newpassword1"}).status_code == 200


def test_change_password_revokes_other_sessions(client, new_client):
    register(client, "alice")
    other = new_client()
    other.cookies.set("hi_session", client.cookies.get("hi_session"))
    assert other.get("/api/auth/me").status_code == 200
    ok = client.post("/api/auth/password", json={"old_password": PASSWORD, "new_password": "newpassword1"})
    assert ok.status_code == 204
    assert other.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me").status_code == 200


def test_session_without_version_is_rejected(client, new_client):
    import base64
    import json

    from itsdangerous import TimestampSigner

    user = register(client, "alice")
    payload = base64.b64encode(json.dumps({"uid": user["id"]}).encode())
    old_cookie = TimestampSigner("test-secret").sign(payload).decode()
    other = new_client()
    other.cookies.set("hi_session", old_cookie)
    r = other.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "请先登录"
