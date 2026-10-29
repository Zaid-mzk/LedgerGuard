from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from app.core.config import settings

password_hash = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hash.verify(hashed, password)
    except (VerifyMismatchError, VerificationError):
        return False



def create_token(user_id: str, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    token_minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.jwt_access_token_minutes
    )
    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(minutes=token_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
