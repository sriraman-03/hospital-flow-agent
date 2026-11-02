from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.permissions import ROLE_PERMISSIONS
from app.schemas.auth import ChangePassword, LoginRequest, MeOut, TokenOut
from app.schemas.common import Message
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(user) -> MeOut:
    out = MeOut.model_validate(user)
    out.permissions = sorted(ROLE_PERMISSIONS.get(user.role, set()))
    return out


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, db: DB):
    user, token = user_service.authenticate(db, body.email, body.password)
    return TokenOut(access_token=token, user=_me(user))


@router.post("/logout", response_model=Message)
def logout(user: CurrentUser, db: DB):
    user_service.logout(db, user)
    return Message(message="Logged out")


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser):
    return _me(user)


@router.post("/change-password", response_model=Message)
def change_password(body: ChangePassword, user: CurrentUser, db: DB):
    user_service.change_password(db, user, body.current_password, body.new_password)
    return Message(message="Password changed. Please sign in again.")
