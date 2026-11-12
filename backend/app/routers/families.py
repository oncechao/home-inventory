import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, member_family
from app.models import Family, Invite, Membership, User, as_utc, utcnow
from app.schemas import FamilyDetail, FamilyIn, FamilyOut, InviteOut, MemberOut
from app.services import delete_family, lock_family

INVITE_TTL = timedelta(days=7)

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
    if not lock_family(db, family.id):
        raise HTTPException(status_code=404, detail="家庭不存在")
    delete_family(db, family.id)
    db.commit()


@router.delete("/{family_id}/members/{user_id}", status_code=204)
def remove_member(
    user_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    """移除成员；user_id 是自己时就是退出家庭。最后一个人离开时删除整个家庭。"""
    if not lock_family(db, family.id):
        raise HTTPException(status_code=404, detail="家庭不存在")
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


@router.get("/{family_id}/invites", response_model=list[InviteOut])
def list_invites(family: Family = Depends(member_family), db: Session = Depends(get_db)):
    now = utcnow()
    invites = db.scalars(
        select(Invite)
        .where(Invite.family_id == family.id, Invite.revoked_at.is_(None))
        .order_by(Invite.created_at.desc())
    ).all()
    return [i for i in invites if as_utc(i.expires_at) > now]


@router.post("/{family_id}/invites", status_code=201, response_model=InviteOut)
def create_invite(
    family: Family = Depends(member_family),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    invite = Invite(
        family_id=family.id,
        code=secrets.token_urlsafe(9),  # 12 个字符，URL 安全
        created_by=user.id,
        expires_at=utcnow() + INVITE_TTL,
    )
    db.add(invite)
    db.commit()
    return invite


@router.delete("/{family_id}/invites/{invite_id}", status_code=204)
def revoke_invite(
    invite_id: uuid.UUID,
    family: Family = Depends(member_family),
    db: Session = Depends(get_db),
):
    invite = db.get(Invite, invite_id)
    if invite is None or invite.family_id != family.id:
        raise HTTPException(status_code=404, detail="邀请不存在")
    invite.revoked_at = utcnow()
    db.commit()
