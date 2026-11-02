from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role
from app.schemas.common import ORM


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    department_id: int | None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class MeOut(UserOut):
    permissions: list[str] = []


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeOut


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=72)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=72)
    role: Role
    department_id: int | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=120)
    role: Role | None = None
    department_id: int | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=10, max_length=72)
