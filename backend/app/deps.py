import uuid
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import Family, Membership, User
from app.security import session_version


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.session.get("uid")
    user = None
    if raw:
        try:
            user = db.get(User, uuid.UUID(raw))
        except ValueError:
            user = None
    if user is not None and request.session.get("pv") != session_version(user.password_hash):
        user = None
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def member_family(
    family_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Family:
    """路径里的家庭必须是当前账号所在的家庭；否则一律 404，不暴露家庭是否存在。"""
    if db.get(Membership, (user.id, family_id)) is None:
        raise HTTPException(status_code=404, detail="家庭不存在")
    return db.get(Family, family_id)
