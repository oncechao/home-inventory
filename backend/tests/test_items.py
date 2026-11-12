import uuid

import pytest
from sqlalchemy import func, select

from app.models import Item, Location
from helpers import create_family, create_item, create_location, invite_and_join, register


@pytest.fixture
def fam(client):
    register(client, "alice")
    return create_family(client)


def item_names(resp):
    return sorted(i["name"] for i in resp.json())


def test_create_item_with_path(client, fam):
    room = create_location(client, fam, "书房")
    drawer = create_location(client, fam, "左侧抽屉", room)
    iid = create_item(client, fam, "护照", drawer, note="在文件袋里")
    item = client.get(f"/api/families/{fam}/items/{iid}").json()
    assert [n["name"] for n in item["path"]] == ["书房", "左侧抽屉"]
    assert item["barcode"] is None
    assert item["updated_by_name"] == "alice"


def test_location_must_exist(client, fam):
    r = client.post(
        f"/api/families/{fam}/items", json={"name": "x", "location_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "位置不存在"


def test_empty_barcode_is_null(client, fam):
    loc = create_location(client, fam, "客厅")
    iid = create_item(client, fam, "遥控器", loc, barcode="  ")
    assert client.get(f"/api/families/{fam}/items/{iid}").json()["barcode"] is None


def test_search_by_name_barcode_and_note(client, fam):
    loc = create_location(client, fam, "厨房")
    create_item(client, fam, "Sharp Knife", loc)
    create_item(client, fam, "洗洁精", loc, barcode="6901234567890")
    create_item(client, fam, "保鲜膜", loc, note="备用的在上层")
    base = f"/api/families/{fam}/items"
    assert item_names(client.get(base, params={"q": "knife"})) == ["Sharp Knife"]
    assert item_names(client.get(base, params={"q": "洁精"})) == ["洗洁精"]
    assert item_names(client.get(base, params={"q": "1234567"})) == ["洗洁精"]
    assert item_names(client.get(base, params={"q": "备用"})) == ["保鲜膜"]
    assert len(client.get(base).json()) == 3  # 不带条件时返回最近更新的物品


def test_search_escapes_wildcards(client, fam):
    loc = create_location(client, fam, "衣柜")
    create_item(client, fam, "100%纯棉T恤", loc)
    create_item(client, fam, "毛衣", loc)
    assert item_names(client.get(f"/api/families/{fam}/items", params={"q": "%"})) == ["100%纯棉T恤"]
    assert item_names(client.get(f"/api/families/{fam}/items", params={"q": "_"})) == []


def test_barcode_matches_multiple_items(client, fam):
    a = create_location(client, fam, "浴室")
    b = create_location(client, fam, "储物间")
    create_item(client, fam, "洗发水", a, barcode="6900000000001")
    create_item(client, fam, "洗发水（备用）", b, barcode="6900000000001")
    base = f"/api/families/{fam}/items"
    assert item_names(client.get(base, params={"barcode": "6900000000001"})) == ["洗发水", "洗发水（备用）"]
    assert client.get(base, params={"barcode": "000"}).json() == []


def test_update_and_move_item(client, fam):
    a = create_location(client, fam, "客厅")
    b = create_location(client, fam, "卧室")
    iid = create_item(client, fam, "充电器", a, barcode="123")
    r = client.patch(
        f"/api/families/{fam}/items/{iid}",
        json={"location_id": b, "name": "手机充电器", "barcode": None},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "手机充电器"
    assert body["barcode"] is None
    assert [n["name"] for n in body["path"]] == ["卧室"]


def test_location_detail_lists_items_and_blocks_delete(client, fam):
    loc = create_location(client, fam, "玄关")
    iid = create_item(client, fam, "钥匙", loc)
    detail = client.get(f"/api/families/{fam}/locations/{loc}").json()
    assert [i["name"] for i in detail["items"]] == ["钥匙"]
    assert client.delete(f"/api/families/{fam}/locations/{loc}").status_code == 409
    assert client.delete(f"/api/families/{fam}/items/{iid}").status_code == 204
    assert client.get(f"/api/families/{fam}/items/{iid}").status_code == 404
    assert client.delete(f"/api/families/{fam}/locations/{loc}").status_code == 204


def test_dissolving_family_deletes_its_data(app, client, fam):
    room = create_location(client, fam, "书房")
    box = create_location(client, fam, "盒子", room)
    create_item(client, fam, "U盘", box)
    assert client.delete(f"/api/families/{fam}").status_code == 204
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Item)) == 0
        assert db.scalar(select(func.count()).select_from(Location)) == 0


def test_patch_reports_current_editor(client, new_client, fam):
    loc = create_location(client, fam, "客厅")
    iid = create_item(client, fam, "遥控器", loc)
    bob = new_client()
    register(bob, "bob")
    invite_and_join(client, bob, fam)
    r = bob.patch(f"/api/families/{fam}/items/{iid}", json={"note": "在沙发上"})
    assert r.json()["updated_by_name"] == "bob"
