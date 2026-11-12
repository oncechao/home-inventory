import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Family, Invite, Item, Location, Membership


def delete_family(db: Session, family_id: uuid.UUID) -> None:
    """按依赖顺序删除一个家庭的全部数据。调用方负责 commit。"""
    db.execute(delete(Item).where(Item.family_id == family_id))
    db.execute(delete(Location).where(Location.family_id == family_id))
    db.execute(delete(Invite).where(Invite.family_id == family_id))
    db.execute(delete(Membership).where(Membership.family_id == family_id))
    db.execute(delete(Family).where(Family.id == family_id))
