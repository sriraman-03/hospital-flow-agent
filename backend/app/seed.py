"""Reproducible SYNTHETIC demo data. Development use only.

    python -m app.seed            # idempotent: does nothing if data already exists
    python -m app.seed --reset    # wipes all tables first (refuses in production)

Demo user password comes from SEED_USER_PASSWORD; if unset a random one is generated and printed once.
"""
import argparse
import random
import secrets
from datetime import date, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.db.types import utcnow
import app.models  # noqa: F401
from app.models.enums import BedStatus, DepartmentStatus, Role
from app.models.hospital import Bed, Department, Patient
from app.models.inventory import Resource
from app.models.user import User
from app.services import bed_service, capacity_service, discharge_service, patient_service, resource_service, user_service

DEPARTMENTS = [
    ("Emergency", "ED", 20, 8), ("Intensive Care", "ICU", 10, 8), ("General Medicine", "GM", 40, 16),
    ("Surgery", "SUR", 24, 10), ("Maternity", "MAT", 16, 8), ("Paediatrics", "PED", 16, 8),
]
RESOURCES = [  # name, category, unit, qty, min, critical, dept code or None, location
    ("Examination gloves (M)", "PPE", "boxes", 240, 100, 40, None, "Central Store"),
    ("N95 masks", "PPE", "boxes", 60, 80, 30, None, "Central Store"),
    ("Surgical masks", "PPE", "boxes", 400, 150, 60, None, "Central Store"),
    ("Isolation gowns", "PPE", "packs", 35, 50, 20, "ED", "ED Supply Room"),
    ("Oxygen cylinders (large)", "Oxygen", "cylinders", 14, 20, 8, "ICU", "ICU Store"),
    ("Oxygen cylinders (portable)", "Oxygen", "cylinders", 55, 25, 10, None, "Central Store"),
    ("IV fluid sets", "Consumables", "units", 520, 200, 80, "GM", "Ward Store"),
    ("Sterile dressings", "Consumables", "packs", 150, 60, 25, "SUR", "Theatre Store"),
    ("Disposable syringes", "Consumables", "boxes", 18, 40, 15, None, "Central Store"),
    ("Hand sanitiser", "Hygiene", "litres", 90, 30, 10, None, "Central Store"),
]
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Quinn", "Drew", "Robin", "Kai", "Noor", "Ravi", "Mei"]
LAST = ["Demo", "Sample", "Testcase", "Example", "Synthetic", "Mockley", "Fakeman", "Placeholder", "Dummy", "Trial"]


def reset() -> None:
    if get_settings().is_production:
        raise SystemExit("Refusing to reset a production database")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if get_settings().is_production:
        raise SystemExit("Demo seeding is disabled when ENVIRONMENT=production. Use `python -m app.cli create-admin`.")
    if args.reset:
        reset()
    rng = random.Random(42)  # deterministic
    db = SessionLocal()
    try:
        if db.scalar(select(User.id).limit(1)):
            print("Database already contains data; nothing to do (use --reset to rebuild).")
            return
        password = get_settings().seed_user_password or secrets.token_urlsafe(14)
        generated = not get_settings().seed_user_password

        admin = user_service.create_user(db, None, email="admin@demo.hospital", full_name="Demo Administrator", password=password, role=Role.ADMIN.value, department_id=None)
        user_service.create_user(db, None, email="ops@demo.hospital", full_name="Demo Operations", password=password, role=Role.OPERATIONS.value, department_id=None)
        user_service.create_user(db, None, email="viewer@demo.hospital", full_name="Demo Viewer", password=password, role=Role.VIEWER.value, department_id=None)

        depts: dict[str, Department] = {}
        for name, code, cap, bed_count in DEPARTMENTS:
            d = Department(name=name, code=code, capacity=cap, description=f"{name} department (synthetic)", status=DepartmentStatus.ACTIVE.value)
            db.add(d)
            db.flush()
            depts[code] = d
            for i in range(1, bed_count + 1):
                db.add(Bed(code=f"{code}-{i:02d}", department_id=d.id, ward=f"{name} Ward {'A' if i <= bed_count // 2 else 'B'}"))
        db.commit()
        user_service.create_user(db, admin, email="dept@demo.hospital", full_name="Demo Department Staff", password=password,
                                 role=Role.DEPARTMENT.value, department_id=depts["GM"].id)

        for name, cat, unit, qty, mn, crit, dcode, loc in RESOURCES:
            resource_service.create_resource(db, admin, {
                "name": name, "category": cat, "unit": unit, "quantity": qty, "min_threshold": mn, "critical_threshold": crit,
                "department_id": depts[dcode].id if dcode else None, "storage_location": loc})

        # Patients: admit most into departments with beds; leave some registered / pending / discharged
        codes = list(depts)
        for n in range(40):
            p = patient_service.register(db, admin, {
                "first_name": rng.choice(FIRST), "last_name": f"{rng.choice(LAST)}{n:02d}",
                "date_of_birth": date.today() - timedelta(days=rng.randint(1, 90) * 365 + rng.randint(0, 364)),
                "phone": None})
            if n < 28:
                dept = depts[codes[n % len(codes)]]
                free = db.scalar(select(Bed).where(Bed.department_id == dept.id, Bed.status == BedStatus.AVAILABLE.value).limit(1))
                patient_service.admit(db, admin, p.id, dept.id, free.id if free and n % 7 else None)
                p.admitted_at = utcnow() - timedelta(days=rng.randint(0, 12), hours=rng.randint(0, 23))
                db.commit()
            elif n < 32:
                patient_service.request_admission(db, admin, p.id, depts["ED"].id)
        # a few completed discharges for the analytics chart
        for p in list(db.scalars(select(Patient).where(Patient.status == "admitted").limit(5))):
            d = discharge_service.request_discharge(db, admin, p.id, "Synthetic demo discharge")
            if d.status != "approved":
                discharge_service.approve(db, admin, d.id)
            discharge_service.complete(db, admin, d.id)
        for d in depts.values():
            capacity_service.evaluate_department_capacity(db, d.id)
        db.commit()

        print("Seed complete (synthetic data).")
        print("Demo users: admin@demo.hospital, ops@demo.hospital, dept@demo.hospital, viewer@demo.hospital")
        print(f"Password: {password}" + ("   <- generated; shown only once" if generated else "   (from SEED_USER_PASSWORD)"))
    finally:
        db.close()


if __name__ == "__main__":
    main()
