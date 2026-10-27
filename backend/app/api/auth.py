from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.models import User
from app.schemas import Login, Register, TokenRead, UserRead
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: Register, session: Database):
    # Hash before the first query acquires the write lock.
    hashed = hash_password(data.password)
    if session.scalar(select(User.id).where(User.username == data.username)) is not None:
        raise HTTPException(409, "用户名已存在")
    user = User(username=data.username, display_name=data.display_name, password_hash=hashed)
    session.add(user)
    session.flush()
    return user


@router.post("/login", response_model=TokenRead)
def login(data: Login, request: Request, session: Database):
    user = session.scalar(select(User).where(User.username == data.username))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        raise HTTPException(401, "用户名或密码错误", headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    return TokenRead(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser):
    return user
