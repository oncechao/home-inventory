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


def create_location(client, fid, name, parent_id=None):
    r = client.post(f"/api/families/{fid}/locations", json={"name": name, "parent_id": parent_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def create_item(client, fid, name, location_id, barcode=None, note=""):
    r = client.post(
        f"/api/families/{fid}/items",
        json={"name": name, "location_id": location_id, "barcode": barcode, "note": note},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]
