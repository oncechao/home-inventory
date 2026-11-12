PASSWORD = "password123"


def register(client, username):
    r = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def create_family(client, name="我家"):
    r = client.post("/api/families", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def invite_and_join(owner, joiner, fid):
    code = owner.post(f"/api/families/{fid}/invites").json()["code"]
    r = joiner.post(f"/api/invites/{code}/accept")
    assert r.status_code == 200, r.text
