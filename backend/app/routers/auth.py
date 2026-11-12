from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import User
from app.schemas import LoginIn, PasswordIn, RegisterIn, UserOut
from app.security import hash_password, session_version, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# 用户不存在时也做一次哈希校验，让响应时间和“密码错误”一致，避免探测用户名
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _log_in(request: Request, user: User) -> None:
    request.session["uid"] = str(user.id)
    request.session["pv"] = session_version(user.password_hash)


@router.post("/register", status_code=201, response_model=UserOut)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # 并发注册同名
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名已被占用")
    _log_in(request, user)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None:
        verify_password(_DUMMY_HASH, body.password)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    _log_in(request, user)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/password", status_code=204)
def change_password(
    body: PasswordIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(user.password_hash, body.old_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    # 当前设备保持登录，其他设备的旧 Cookie 失效
    request.session["pv"] = session_version(user.password_hash)
