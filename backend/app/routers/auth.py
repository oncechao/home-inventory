from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import User
from app.schemas import LoginIn, PasswordIn, RegisterIn, UserOut
from app.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


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
    request.session["uid"] = str(user.id)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    request.session["uid"] = str(user.id)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/password", status_code=204)
def change_password(
    body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if not verify_password(user.password_hash, body.old_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    db.commit()
