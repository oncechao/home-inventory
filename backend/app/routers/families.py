import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Membership, User
from app.schemas import FamilyDetail, FamilyIn, FamilyOut, MemberOut
from app.services import delete_family

router = APIRouter(prefix="/families", tags=["families"])


@router.get("", response_model=list[FamilyOut])
def list_families(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Family)
        .join(Membership, Membership.family_id == Family.id)
        .where(Membership.user_id == user.id)
        .order_by(Membership.joined_at)
    )
    return db.scalars(stmt).all()


@router.post("", status_code=201, response_model=FamilyOut)
def create_family(
    body: FamilyIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    family = Family(name=body.name)
    db.add(family)
    db.flush()
    db.add(Membership(user_id=user.id, family_id=family.id))
    db.commit()
    return family


@router.get("/{family_id}", response_model=FamilyDetail)
def get_family(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    memberships = db.scalars(
        select(Membership)
        .where(Membership.family_id == family.id)
        .order_by(Membership.joined_at)
    ).all()
    return FamilyDetail(
        id=family.id,
        name=family.name,
        members=[
            MemberOut(id=m.user.id, username=m.user.username, joined_at=m.joined_at)
            for m in memberships
        ],
    )


@router.patch("/{family_id}", response_model=FamilyOut)
def rename_family(
    body: FamilyIn, family: Family = Depends(member_family), db: Session = Depends(get_db)
):
    family.name = body.name
    db.commit()
    return family


@router.delete("/{family_id}", status_code=204)
def dissolve_family(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    delete_family(db, family.id)
    db.commit()


@router.delete("/{family_id}/members/{user_id}", status_code=204)
def remove_member(
    user_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    """移除成员；user_id 是自己时就是退出家庭。最后一个人离开时删除整个家庭。"""
    membership = db.get(Membership, (user_id, family.id))
    if membership is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    db.delete(membership)
    db.flush()
    remaining = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.family_id == family.id)
    )
    if remaining == 0:
        delete_family(db, family.id)
    db.commit()
