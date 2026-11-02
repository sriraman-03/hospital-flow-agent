from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ForbiddenError
from app.core.permissions import has_permission
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]


def user_from_token(db: Session, token: str) -> User:
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AuthError("Invalid or expired token") from None
    user = db.get(User, user_id)
    if not user or not user.is_active or user.token_version != payload.get("tv"):
        raise AuthError("Invalid or expired token")
    return user


def get_current_user(db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User:
    if creds is None:
        raise AuthError("Not authenticated")
    return user_from_token(db, creds.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(permission: str):
    def checker(user: CurrentUser) -> User:
        if not has_permission(user.role, permission):
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return checker


def page_params(page: int = 1, page_size: int = 25) -> tuple[int, int]:
    return max(1, page), min(max(1, page_size), 200)
