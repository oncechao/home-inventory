from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Family, Invite, Membership, User, as_utc, utcnow
from app.schemas import FamilyOut, InvitePreview
from app.services import lock_family

router = APIRouter(prefix="/invites", tags=["invites"])


def _valid_invite(db: Session, code: str) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.code == code))
    if invite is None or invite.revoked_at is not None or as_utc(invite.expires_at) <= utcnow():
        raise HTTPException(status_code=404, detail="邀请无效或已过期")
    return invite


@router.get("/{code}", response_model=InvitePreview)
def preview_invite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    invite = _valid_invite(db, code)
    family = db.get(Family, invite.family_id)
    return InvitePreview(
        family_id=family.id,
        family_name=family.name,
        already_member=db.get(Membership, (user.id, family.id)) is not None,
    )


@router.post("/{code}/accept", response_model=FamilyOut)
def accept_invite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    invite = _valid_invite(db, code)
    family_id = invite.family_id
    if not lock_family(db, family_id):
        raise HTTPException(status_code=404, detail="邀请无效或已过期")
    if db.get(Membership, (user.id, family_id)) is None:
        db.add(Membership(user_id=user.id, family_id=family_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # 并发重复接受：成员关系已经存在
    return db.get(Family, family_id)
