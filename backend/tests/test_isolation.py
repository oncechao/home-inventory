import pytest

from helpers import create_family, create_item, create_location, register


@pytest.fixture
def world(client, new_client):
    """alice 在 A 家庭，bob 在 B 家庭，各自有位置和物品。"""
    alice = register(client, "alice")
    fa = create_family(client, "A家")
    loc_a = create_location(client, fa, "A的客厅")
    item_a = create_item(client, fa, "A的护照", loc_a, barcode="111")
    invite_a = client.post(f"/api/families/{fa}/invites").json()["id"]

    bob = new_client()
    register(bob, "bob")
    fb = create_family(bob, "B家")
    loc_b = create_location(bob, fb, "B的客厅")
    item_b = create_item(bob, fb, "B的钥匙", loc_b)
    return {
        "alice": alice, "bob": bob, "fa": fa, "fb": fb,
        "loc_a": loc_a, "item_a": item_a, "invite_a": invite_a,
        "loc_b": loc_b, "item_b": item_b,
    }


@pytest.mark.parametrize(
    "method,url,body",
    [
        # 直接访问 A 家庭的路径
        ("get", "/api/families/{fa}", None),
        ("get", "/api/families/{fa}/locations", None),
        ("get", "/api/families/{fa}/locations/{loc_a}", None),
        ("patch", "/api/families/{fa}/locations/{loc_a}", {"name": "x"}),
        ("delete", "/api/families/{fa}/locations/{loc_a}", None),
        ("post", "/api/families/{fa}/locations", {"name": "x"}),
        ("get", "/api/families/{fa}/items", None),
        ("get", "/api/families/{fa}/items/{item_a}", None),
        ("patch", "/api/families/{fa}/items/{item_a}", {"name": "x"}),
        ("delete", "/api/families/{fa}/items/{item_a}", None),
        ("get", "/api/families/{fa}/invites", None),
        ("delete", "/api/families/{fa}/invites/{invite_a}", None),
        ("delete", "/api/families/{fa}/members/{alice_id}", None),
        # 借自己家庭 B 的路径，夹带 A 家庭的 ID
        ("get", "/api/families/{fb}/locations/{loc_a}", None),
        ("patch", "/api/families/{fb}/locations/{loc_a}", {"name": "x"}),
        ("delete", "/api/families/{fb}/locations/{loc_a}", None),
        ("get", "/api/families/{fb}/items/{item_a}", None),
        ("patch", "/api/families/{fb}/items/{item_a}", {"name": "x"}),
        ("delete", "/api/families/{fb}/items/{item_a}", None),
        ("delete", "/api/families/{fb}/invites/{invite_a}", None),
        ("delete", "/api/families/{fb}/members/{alice_id}", None),
        # 把 A 家庭的位置当作上级位置或存放位置
        ("post", "/api/families/{fb}/locations", {"name": "x", "parent_id": "{loc_a}"}),
        ("patch", "/api/families/{fb}/locations/{loc_b}", {"parent_id": "{loc_a}"}),
        ("post", "/api/families/{fb}/items", {"name": "x", "location_id": "{loc_a}"}),
        ("patch", "/api/families/{fb}/items/{item_b}", {"location_id": "{loc_a}"}),
        # 二维码入口
        ("get", "/api/locations/{loc_a}", None),
    ],
)
def test_bob_cannot_touch_family_a(world, method, url, body):
    ids = {k: v for k, v in world.items() if isinstance(v, str)}
    ids["alice_id"] = world["alice"]["id"]
    url = url.format(**ids)
    if body:
        body = {k: v.format(**ids) if isinstance(v, str) else v for k, v in body.items()}
    r = getattr(world["bob"], method)(url, **({"json": body} if body else {}))
    assert r.status_code == 404, (method, url, r.text)


def test_search_never_leaks_other_family(world):
    bob, fb = world["bob"], world["fb"]
    assert bob.get(f"/api/families/{fb}/items", params={"q": "护照"}).json() == []
    assert bob.get(f"/api/families/{fb}/items", params={"barcode": "111"}).json() == []
    assert [l["name"] for l in bob.get(f"/api/families/{fb}/locations").json()] == ["B的客厅"]


def test_family_a_data_unchanged(world, client):
    fa = world["fa"]
    assert client.get(f"/api/families/{fa}/items/{world['item_a']}").json()["name"] == "A的护照"
    assert client.get(f"/api/families/{fa}/locations/{world['loc_a']}").json()["name"] == "A的客厅"
