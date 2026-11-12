import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Item, Location, Membership, User
from app.schemas import LocationDetail, LocationIn, LocationOut, LocationPatch
from app.services import (
    get_location_in_family,
    item_out,
    location_out,
    location_paths,
    would_create_cycle,
)

router = APIRouter(prefix="/families/{family_id}/locations", tags=["locations"])
lookup_router = APIRouter(tags=["locations"])


@router.get("", response_model=list[LocationOut])
def list_locations(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    paths = location_paths(db, family.id)
    locations = db.scalars(select(Location).where(Location.family_id == family.id)).all()
    return sorted(
        (location_out(l, paths) for l in locations),
        key=lambda out: [node.name for node in out.path],
    )


@router.post("", status_code=201, response_model=LocationOut)
def create_location(
    body: LocationIn,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if body.parent_id is not None:
        get_location_in_family(db, family.id, body.parent_id, "上级位置不存在")
    location = Location(
        family_id=family.id,
        parent_id=body.parent_id,
        name=body.name,
        note=body.note,
        updated_by=user.id,
    )
    db.add(location)
    db.commit()
    return location_out(location, location_paths(db, family.id))


@router.get("/{location_id}", response_model=LocationDetail)
def get_location(
    location_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    location = get_location_in_family(db, family.id, location_id)
    paths = location_paths(db, family.id)
    children = db.scalars(
        select(Location).where(Location.parent_id == location.id).order_by(Location.name)
    ).all()
    items = db.scalars(
        select(Item).where(Item.location_id == location.id).order_by(Item.name)
    ).all()
    return LocationDetail(
        **location_out(location, paths).model_dump(),
        children=[location_out(c, paths) for c in children],
        items=[item_out(i, paths) for i in items],
    )


@router.patch("/{location_id}", response_model=LocationOut)
def update_location(
    location_id: uuid.UUID,
    body: LocationPatch,
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    location = get_location_in_family(db, family.id, location_id)
    if body.name is not None:
        location.name = body.name
    if body.note is not None:
        location.note = body.note
    if "parent_id" in body.model_fields_set:
        if body.parent_id is not None:
            get_location_in_family(db, family.id, body.parent_id, "上级位置不存在")
            if would_create_cycle(db, family.id, location.id, body.parent_id):
                raise HTTPException(status_code=409, detail="不能移动到它自己或它的下级位置里")
        location.parent_id = body.parent_id
    location.updated_by = user.id
    location.updater = user
    db.commit()
    return location_out(location, location_paths(db, family.id))


@router.delete("/{location_id}", status_code=204)
def delete_location(
    location_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    location = get_location_in_family(db, family.id, location_id)
    has_child = db.scalar(select(Location.id).where(Location.parent_id == location.id).limit(1))
    has_item = db.scalar(select(Item.id).where(Item.location_id == location.id).limit(1))
    if has_child or has_item:
        raise HTTPException(status_code=409, detail="位置里还有子位置或物品，请先移走")
    db.delete(location)
    db.commit()


@lookup_router.get("/locations/{location_id}")
def lookup_location(
    location_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """二维码入口：告诉前端这个位置属于哪个家庭。不是成员时 404。"""
    location = db.get(Location, location_id)
    if location is None or db.get(Membership, (user.id, location.family_id)) is None:
        raise HTTPException(status_code=404, detail="位置不存在")
    return {"family_id": str(location.family_id)}
