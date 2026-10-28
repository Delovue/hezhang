from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import Settings

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("not-a-real-user-password")
ISSUER = "hezhang"
AUDIENCE = "hezhang-api"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hasher.verify(password, hashed)


def create_access_token(user_id: int, settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
            "iss": ISSUER,
            "aud": AUDIENCE,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> int:
    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={"require": ["sub", "iat", "exp", "iss", "aud"]},
    )
    subject = payload["sub"]
    if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
        raise jwt.InvalidTokenError("Invalid subject")
    user_id = int(subject)
    if user_id <= 0:
        raise jwt.InvalidTokenError("Invalid subject")
    return user_id
