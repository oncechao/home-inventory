import uuid

import pytest

from helpers import create_family, create_location, invite_and_join, register


@pytest.fixture
def fam(client):
    register(client, "alice")
    return create_family(client)


def names(path):
    return [n["name"] for n in path]


def test_nested_locations_have_full_path(client, fam):
    bedroom = create_location(client, fam, "主卧")
    wardrobe = create_location(client, fam, "衣柜", bedroom)
    box = create_location(client, fam, "蓝色收纳盒", wardrobe)

    detail = client.get(f"/api/families/{fam}/locations/{box}").json()
    assert names(detail["path"]) == ["主卧", "衣柜", "蓝色收纳盒"]
    assert detail["updated_by_name"] == "alice"

    wardrobe_detail = client.get(f"/api/families/{fam}/locations/{wardrobe}").json()
    assert [c["name"] for c in wardrobe_detail["children"]] == ["蓝色收纳盒"]


def test_list_is_sorted_by_path(client, fam):
    study = create_location(client, fam, "书房")
    bedroom = create_location(client, fam, "主卧")
    create_location(client, fam, "书桌", study)
    create_location(client, fam, "衣柜", bedroom)
    listed = client.get(f"/api/families/{fam}/locations").json()
    assert [" › ".join(names(l["path"])) for l in listed] == sorted(
        ["书房", "书房 › 书桌", "主卧", "主卧 › 衣柜"]
    )


def test_parent_must_exist(client, fam):
    r = client.post(
        f"/api/families/{fam}/locations", json={"name": "x", "parent_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "上级位置不存在"


def test_rename_and_note(client, fam):
    loc = create_location(client, fam, "客厅")
    r = client.patch(f"/api/families/{fam}/locations/{loc}", json={"name": "大客厅", "note": "电视柜"})
    assert r.status_code == 200
    assert r.json()["name"] == "大客厅"
    assert r.json()["note"] == "电视柜"
    assert r.json()["parent_id"] is None  # 没传 parent_id 时不改动


def test_move_location(client, fam):
    bedroom = create_location(client, fam, "主卧")
    study = create_location(client, fam, "书房")
    wardrobe = create_location(client, fam, "衣柜", bedroom)
    box = create_location(client, fam, "盒子", wardrobe)

    r = client.patch(f"/api/families/{fam}/locations/{wardrobe}", json={"parent_id": study})
    assert r.status_code == 200
    box_path = client.get(f"/api/families/{fam}/locations/{box}").json()["path"]
    assert names(box_path) == ["书房", "衣柜", "盒子"]

    r = client.patch(f"/api/families/{fam}/locations/{wardrobe}", json={"parent_id": None})
    assert names(r.json()["path"]) == ["衣柜"]


def test_cannot_move_into_itself_or_descendant(client, fam):
    a = create_location(client, fam, "A")
    b = create_location(client, fam, "B", a)
    c = create_location(client, fam, "C", b)
    for target in (a, b, c):
        r = client.patch(f"/api/families/{fam}/locations/{a}", json={"parent_id": target})
        assert r.status_code == 409, target
        assert r.json()["detail"] == "不能移动到它自己或它的下级位置里"


def test_delete_only_empty_location(client, fam):
    parent = create_location(client, fam, "主卧")
    child = create_location(client, fam, "衣柜", parent)
    r = client.delete(f"/api/families/{fam}/locations/{parent}")
    assert r.status_code == 409
    assert r.json()["detail"] == "位置里还有子位置或物品，请先移走"
    assert client.delete(f"/api/families/{fam}/locations/{child}").status_code == 204
    assert client.delete(f"/api/families/{fam}/locations/{parent}").status_code == 204
    assert client.get(f"/api/families/{fam}/locations").json() == []


def test_lookup_returns_family_for_member(client, new_client, fam):
    loc = create_location(client, fam, "客厅")
    assert client.get(f"/api/locations/{loc}").json() == {"family_id": fam}
    bob = new_client()
    register(bob, "bob")
    assert bob.get(f"/api/locations/{loc}").status_code == 404
    assert client.get(f"/api/locations/{uuid.uuid4()}").status_code == 404


def test_patch_reports_current_editor(client, new_client, fam):
    loc = create_location(client, fam, "客厅")
    bob = new_client()
    register(bob, "bob")
    invite_and_join(client, bob, fam)
    r = bob.patch(f"/api/families/{fam}/locations/{loc}", json={"name": "大客厅"})
    assert r.json()["updated_by_name"] == "bob"
