from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Invite, utcnow
from helpers import create_family, invite_and_join, register


def setup_two(client, new_client):
    alice = register(client, "alice")
    fid = create_family(client, "张家")
    bob_client = new_client()
    bob = register(bob_client, "bob")
    return alice, bob, bob_client, fid


def test_invite_preview_and_accept(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    invite = client.post(f"/api/families/{fid}/invites")
    assert invite.status_code == 201
    code = invite.json()["code"]

    preview = bob.get(f"/api/invites/{code}").json()
    assert preview == {"family_id": fid, "family_name": "张家", "already_member": False}

    r = bob.post(f"/api/invites/{code}/accept")
    assert r.status_code == 200
    assert r.json()["id"] == fid
    assert [f["id"] for f in bob.get("/api/families").json()] == [fid]
    members = client.get(f"/api/families/{fid}").json()["members"]
    assert [m["username"] for m in members] == ["alice", "bob"]


def test_accept_twice_is_ok(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    code = client.post(f"/api/families/{fid}/invites").json()["code"]
    assert bob.post(f"/api/invites/{code}/accept").status_code == 200
    assert bob.get(f"/api/invites/{code}").json()["already_member"] is True
    assert bob.post(f"/api/invites/{code}/accept").status_code == 200
    assert len(client.get(f"/api/families/{fid}").json()["members"]) == 2


def test_revoked_invite_rejected(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    invite = client.post(f"/api/families/{fid}/invites").json()
    assert client.delete(f"/api/families/{fid}/invites/{invite['id']}").status_code == 204
    assert client.get(f"/api/families/{fid}/invites").json() == []
    r = bob.post(f"/api/invites/{invite['code']}/accept")
    assert r.status_code == 404
    assert r.json()["detail"] == "邀请无效或已过期"


def test_expired_invite_rejected(app, client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    code = client.post(f"/api/families/{fid}/invites").json()["code"]
    with app.state.SessionLocal() as db:
        invite = db.scalar(select(Invite).where(Invite.code == code))
        invite.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert bob.get(f"/api/invites/{code}").status_code == 404
    assert bob.post(f"/api/invites/{code}/accept").status_code == 404
    assert client.get(f"/api/families/{fid}/invites").json() == []


def test_invite_expires_in_7_days(client):
    register(client, "alice")
    fid = create_family(client)
    before = utcnow()
    invite = client.post(f"/api/families/{fid}/invites").json()
    expires_at = datetime.fromisoformat(invite["expires_at"])
    assert expires_at.tzinfo is not None
    week = timedelta(days=7)
    assert before + week - timedelta(minutes=1) <= expires_at <= utcnow() + week + timedelta(seconds=1)
    assert len(client.get(f"/api/families/{fid}/invites").json()) == 1


def test_preview_requires_login(client, new_client):
    register(client, "alice")
    fid = create_family(client)
    code = client.post(f"/api/families/{fid}/invites").json()["code"]
    assert new_client().get(f"/api/invites/{code}").status_code == 401


def test_non_member_cannot_manage_invites(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    assert bob.post(f"/api/families/{fid}/invites").status_code == 404
    assert bob.get(f"/api/families/{fid}/invites").status_code == 404


def test_member_can_remove_other_member(client, new_client):
    _, bob_user, bob, fid = setup_two(client, new_client)
    invite_and_join(client, bob, fid)
    assert client.delete(f"/api/families/{fid}/members/{bob_user['id']}").status_code == 204
    assert bob.get(f"/api/families/{fid}").status_code == 404


def test_member_can_leave_and_family_stays(client, new_client):
    _, bob_user, bob, fid = setup_two(client, new_client)
    invite_and_join(client, bob, fid)
    assert bob.delete(f"/api/families/{fid}/members/{bob_user['id']}").status_code == 204
    assert bob.get("/api/families").json() == []
    assert [m["username"] for m in client.get(f"/api/families/{fid}").json()["members"]] == ["alice"]


def test_any_member_can_dissolve(client, new_client):
    _, _, bob, fid = setup_two(client, new_client)
    invite_and_join(client, bob, fid)
    assert bob.delete(f"/api/families/{fid}").status_code == 204
    assert client.get("/api/families").json() == []
