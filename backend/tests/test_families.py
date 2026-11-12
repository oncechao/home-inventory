import uuid

from app.models import Family
from helpers import create_family, register


def test_create_list_and_detail(client):
    register(client, "alice")
    fid = create_family(client, "张家")
    assert [f["name"] for f in client.get("/api/families").json()] == ["张家"]
    detail = client.get(f"/api/families/{fid}").json()
    assert detail["name"] == "张家"
    assert [m["username"] for m in detail["members"]] == ["alice"]


def test_user_can_have_multiple_families(client):
    register(client, "alice")
    create_family(client, "自己家")
    create_family(client, "爸妈家")
    assert [f["name"] for f in client.get("/api/families").json()] == ["自己家", "爸妈家"]


def test_rename_family(client):
    register(client, "alice")
    fid = create_family(client, "张家")
    r = client.patch(f"/api/families/{fid}", json={"name": "  新张家  "})
    assert r.status_code == 200
    assert r.json()["name"] == "新张家"


def test_family_name_required(client):
    register(client, "alice")
    assert client.post("/api/families", json={"name": "   "}).status_code == 422


def test_non_member_gets_404(client, new_client):
    register(client, "alice")
    fid = create_family(client)
    bob = new_client()
    register(bob, "bob")
    assert bob.get(f"/api/families/{fid}").status_code == 404
    assert bob.patch(f"/api/families/{fid}", json={"name": "x"}).status_code == 404
    assert bob.delete(f"/api/families/{fid}").status_code == 404
    assert bob.get(f"/api/families/{uuid.uuid4()}").status_code == 404


def test_requires_login(client):
    assert client.get("/api/families").status_code == 401


def test_dissolve_family(app, client):
    register(client, "alice")
    fid = create_family(client)
    assert client.delete(f"/api/families/{fid}").status_code == 204
    assert client.get(f"/api/families/{fid}").status_code == 404
    assert client.get("/api/families").json() == []
    with app.state.SessionLocal() as db:
        assert db.get(Family, uuid.UUID(fid)) is None


def test_last_member_leaving_deletes_family(app, client):
    alice = register(client, "alice")
    fid = create_family(client)
    assert client.delete(f"/api/families/{fid}/members/{alice['id']}").status_code == 204
    assert client.get("/api/families").json() == []
    with app.state.SessionLocal() as db:
        assert db.get(Family, uuid.UUID(fid)) is None


def test_remove_unknown_member_is_404(client):
    register(client, "alice")
    fid = create_family(client)
    assert client.delete(f"/api/families/{fid}/members/{uuid.uuid4()}").status_code == 404
