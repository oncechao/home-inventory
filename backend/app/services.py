import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Family, Invite, Item, Location, Membership
from app.schemas import ItemOut, LocationOut, PathNode


def delete_family(db: Session, family_id: uuid.UUID) -> None:
    """按依赖顺序删除一个家庭的全部数据。调用方负责 commit。"""
    db.execute(delete(Item).where(Item.family_id == family_id))
    db.execute(delete(Location).where(Location.family_id == family_id))
    db.execute(delete(Invite).where(Invite.family_id == family_id))
    db.execute(delete(Membership).where(Membership.family_id == family_id))
    db.execute(delete(Family).where(Family.id == family_id))


def lock_family(db: Session, family_id: uuid.UUID) -> bool:
    """在同一事务里锁住家庭行，串行化成员变动（Postgres 有效，SQLite 忽略）。返回家庭是否还存在。"""
    return db.execute(select(Family.id).where(Family.id == family_id).with_for_update()).first() is not None


def location_paths(db: Session, family_id: uuid.UUID) -> dict[uuid.UUID, list[PathNode]]:
    """一次读出家庭内全部位置，在内存里拼出每个位置的完整路径（从顶层到自己）。"""
    rows = db.execute(
        select(Location.id, Location.parent_id, Location.name).where(
            Location.family_id == family_id
        )
    ).all()
    by_id = {r.id: r for r in rows}
    cache: dict[uuid.UUID, list[PathNode]] = {}

    def path_of(location_id: uuid.UUID) -> list[PathNode]:
        # 迭代往上走，遇到缓存、顶层、不存在的上级或重复节点（数据里有环）就停下，避免无限递归。
        chain: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()
        current: uuid.UUID | None = location_id
        while current in by_id and current not in cache and current not in seen:
            seen.add(current)
            chain.append(current)
            current = by_id[current].parent_id
        prefix = cache[current] if current in cache else []
        for node_id in reversed(chain):
            prefix = prefix + [PathNode(id=node_id, name=by_id[node_id].name)]
            cache[node_id] = prefix
        return cache[location_id]

    return {location_id: path_of(location_id) for location_id in by_id}


def would_create_cycle(
    db: Session, family_id: uuid.UUID, location_id: uuid.UUID, new_parent_id: uuid.UUID
) -> bool:
    """从新的上级位置一路往上找，如果遇到自己，说明会形成循环。"""
    parents = dict(
        db.execute(
            select(Location.id, Location.parent_id).where(Location.family_id == family_id)
        ).all()
    )
    current: uuid.UUID | None = new_parent_id
    seen: set[uuid.UUID] = set()
    while current is not None:
        if current == location_id or current in seen:
            return True  # 数据里已有环时也当作循环，拒绝移动
        seen.add(current)
        current = parents.get(current)
    return False


def get_location_in_family(
    db: Session, family_id: uuid.UUID, location_id: uuid.UUID, detail: str = "位置不存在"
) -> Location:
    location = db.get(Location, location_id)
    if location is None or location.family_id != family_id:
        raise HTTPException(status_code=404, detail=detail)
    return location


def location_out(location: Location, paths: dict[uuid.UUID, list[PathNode]]) -> LocationOut:
    return LocationOut(
        id=location.id,
        name=location.name,
        note=location.note,
        parent_id=location.parent_id,
        path=paths[location.id],
        updated_at=location.updated_at,
        updated_by_name=location.updater.username if location.updater else None,
    )


def item_out(item: Item, paths: dict[uuid.UUID, list[PathNode]]) -> ItemOut:
    return ItemOut(
        id=item.id,
        name=item.name,
        barcode=item.barcode,
        note=item.note,
        location_id=item.location_id,
        path=paths[item.location_id],
        updated_at=item.updated_at,
        updated_by_name=item.updater.username if item.updater else None,
    )


def escape_like(text: str) -> str:
    """让用户输入的 % 和 _ 按字面匹配。配合 ilike(..., escape='\\\\') 使用。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
