import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Item, User
from app.schemas import ItemIn, ItemOut, ItemPatch
from app.services import escape_like, get_location_in_family, item_out, location_paths

router = APIRouter(prefix="/families/{family_id}/items", tags=["items"])


def _get_item(db: Session, family: Family, item_id: uuid.UUID) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.family_id != family.id:
        raise HTTPException(status_code=404, detail="物品不存在")
    return item


@router.get("", response_model=list[ItemOut])
def list_items(
    q: str | None = None,
    barcode: str | None = None,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    """q：按名称/条码/备注模糊搜索；barcode：按条码精确匹配；都不传则返回最近更新的物品。"""
    stmt = select(Item).where(Item.family_id == family.id)
    filtered = False
    if barcode and barcode.strip():
        stmt = stmt.where(Item.barcode == barcode.strip())
        filtered = True
    if q and q.strip():
        pattern = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                Item.name.ilike(pattern, escape="\\"),
                Item.barcode.ilike(pattern, escape="\\"),
                Item.note.ilike(pattern, escape="\\"),
            )
        )
        filtered = True
    stmt = stmt.order_by(Item.updated_at.desc()).limit(200 if filtered else 50)
    paths = location_paths(db, family.id)
    return [item_out(i, paths) for i in db.scalars(stmt).all()]


@router.post("", status_code=201, response_model=ItemOut)
def create_item(
    body: ItemIn,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_location_in_family(db, family.id, body.location_id)
    item = Item(
        family_id=family.id,
        location_id=body.location_id,
        name=body.name,
        barcode=body.barcode,
        note=body.note,
        updated_by=user.id,
    )
    db.add(item)
    db.commit()
    return item_out(item, location_paths(db, family.id))


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: uuid.UUID, family: Family = Depends(member_family), db: Session = Depends(get_db)
):
    return item_out(_get_item(db, family, item_id), location_paths(db, family.id))


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID,
    body: ItemPatch,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item = _get_item(db, family, item_id)
    if body.name is not None:
        item.name = body.name
    if "barcode" in body.model_fields_set:
        item.barcode = body.barcode
    if body.note is not None:
        item.note = body.note
    if body.location_id is not None:
        get_location_in_family(db, family.id, body.location_id)
        item.location_id = body.location_id
    item.updated_by = user.id
    item.updater = user
    db.commit()
    return item_out(item, location_paths(db, family.id))


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: uuid.UUID, family: Family = Depends(member_family), db: Session = Depends(get_db)
):
    db.delete(_get_item(db, family, item_id))
    db.commit()
