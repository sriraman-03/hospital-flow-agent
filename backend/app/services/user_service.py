from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ConflictError, ForbiddenError, NotFoundError, ValidationFailed
from app.core.security import MAX_PASSWORD_BYTES, create_access_token, hash_password, verify_password
from app.db.types import utcnow
from app.models.hospital import Department
from app.models.user import User
from app.services import audit_service

MIN_PASSWORD_LENGTH = 10


def check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationFailed(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValidationFailed(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")


def authenticate(db: Session, email: str, password: str) -> tuple[User, str]:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    # Same error for unknown user / bad password / disabled account (no account enumeration)
    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        audit_service.log_action(db, None, "auth.login_failed", "user", None, None)
        db.commit()
        raise AuthError("Invalid email or password")
    user.last_login_at = utcnow()
    audit_service.log_action(db, user, "auth.login", "user", user.id)
    db.commit()
    return user, create_access_token(user.id, user.role, user.token_version)


def logout(db: Session, user: User) -> None:
    user.token_version += 1  # revokes all outstanding tokens for this user
    audit_service.log_action(db, user, "auth.logout", "user", user.id)
    db.commit()


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.hashed_password):
        raise ValidationFailed("Current password is incorrect")
    check_password_policy(new)
    user.hashed_password = hash_password(new)
    user.token_version += 1
    audit_service.log_action(db, user, "user.change_password", "user", user.id)
    db.commit()


def create_user(db: Session, actor: User | None, *, email: str, full_name: str, password: str, role: str,
                department_id: int | None) -> User:
    check_password_policy(password)
    email = email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise ConflictError("A user with this email already exists")
    if department_id and not db.get(Department, department_id):
        raise NotFoundError("Department not found")
    u = User(email=email, full_name=full_name, hashed_password=hash_password(password), role=role, department_id=department_id)
    db.add(u)
    db.flush()
    audit_service.log_action(db, actor, "user.create", "user", u.id, {"role": role})
    db.commit()
    return u


def update_user(db: Session, actor: User, user_id: int, data: dict) -> User:
    u = db.get(User, user_id)
    if not u:
        raise NotFoundError("User not found")
    if u.id == actor.id and (data.get("is_active") is False or ("role" in data and data["role"] != u.role)):
        raise ForbiddenError("You cannot deactivate or change the role of your own account")
    if data.get("department_id") and not db.get(Department, data["department_id"]):
        raise NotFoundError("Department not found")
    for k, v in data.items():
        setattr(u, k, v)
    if "role" in data or data.get("is_active") is False:
        u.token_version += 1
    audit_service.log_action(db, actor, "user.update", "user", u.id, {"fields_changed": sorted(data)})
    db.commit()
    return u


def reset_password(db: Session, actor: User, user_id: int, new_password: str) -> None:
    u = db.get(User, user_id)
    if not u:
        raise NotFoundError("User not found")
    check_password_policy(new_password)
    u.hashed_password = hash_password(new_password)
    u.token_version += 1
    audit_service.log_action(db, actor, "user.reset_password", "user", u.id)
    db.commit()
