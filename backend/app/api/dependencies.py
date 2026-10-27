from collections.abc import Iterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import transaction
from app.models import User
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Iterator[Session]:
    write = request.method in {"POST", "PATCH", "PUT", "DELETE"}
    if request.url.path == "/api/v1/auth/login":
        write = False
    with transaction(request.app.state.engine, write=write) as session:
        yield session


# Commit/rollback before the HTTP response is sent, including constraint failures.
Database = Annotated[Session, Depends(get_session, scope="function")]


def current_user(
    request: Request,
    session: Database,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        status_code=401, detail="请先登录或重新登录", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id = decode_access_token(credentials.credentials, request.app.state.settings)
    except jwt.InvalidTokenError:
        raise unauthorized from None
    user = session.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(current_user)]
