PASSWORD = "password123"


def register(client, username):
    r = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()
