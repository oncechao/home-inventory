PASSWORD = "password123"


def register(client, username):
    r = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def create_family(client, name="我家"):
    r = client.post("/api/families", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]
