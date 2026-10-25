import os

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import User
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)

FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:5173",
).rstrip("/")


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    cookie_token = request.cookies.get("lg_access_token")

    # Prefer the existing bearer token when one is provided.
    token = credentials.credentials if credentials else cookie_token

    if not token:
        raise HTTPException(
            401,
            detail={"code": "AUTH_REQUIRED", "message": "Sign in to continue"},
        )

    # Require the expected frontend origin for state-changing requests
    # authenticated through the cookie.
    if not credentials and cookie_token:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin", "").rstrip("/")
            if origin != FRONTEND_ORIGIN:
                raise HTTPException(
                    403,
                    detail={
                        "code": "CSRF_CHECK_FAILED",
                        "message": "Request origin is not allowed",
                    },
                )

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            401,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Token is invalid or expired",
            },
        )

    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(
            401,
            detail={"code": "INVALID_USER", "message": "User is unavailable"},
        )

    return user


def roles(*allowed):
    def check(user: User = Depends(current_user)):
        if user.role not in allowed:
            raise HTTPException(
                403,
                detail={
                    "code": "FORBIDDEN",
                    "message": "Your role cannot perform this action",
                },
            )
        return user

    return check
