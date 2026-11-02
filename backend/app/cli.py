"""Administrative CLI.   python -m app.cli create-admin --email you@example.org --name "Your Name"
Prompts for the password (never passed on the command line, never stored in files)."""
import argparse
import getpass

from app.db.session import SessionLocal
from app.models.enums import Role
from app.services import user_service


def main() -> None:
    ap = argparse.ArgumentParser(prog="app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-admin", help="Create an administrator account")
    c.add_argument("--email", required=True)
    c.add_argument("--name", required=True)
    args = ap.parse_args()
    if args.cmd == "create-admin":
        pw = getpass.getpass("Password (min 10 chars): ")
        if pw != getpass.getpass("Repeat password: "):
            raise SystemExit("Passwords do not match")
        db = SessionLocal()
        try:
            u = user_service.create_user(db, None, email=args.email, full_name=args.name, password=pw,
                                         role=Role.ADMIN.value, department_id=None)
            print(f"Administrator created: {u.email}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
