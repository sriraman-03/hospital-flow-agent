import os
import tempfile

# Isolated test database + secrets, set BEFORE the app is imported.
_tmp = tempfile.mkdtemp(prefix="hfa-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-0123456789"
os.environ["ENVIRONMENT"] = "development"
os.environ["LLM_PROVIDER"] = "none"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.models.hospital import Bed, Department  # noqa: E402
from app.services import user_service  # noqa: E402

PASSWORD = "Synthetic-Pass-123"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def users(db):
    out = {}
    for role in Role:
        out[role.value] = user_service.create_user(db, None, email=f"{role.value}@test.local", full_name=role.value,
                                                   password=PASSWORD, role=role.value, department_id=None)
    return out


@pytest.fixture()
def auth(client, users):
    """auth('administrator') -> Authorization headers for that role."""
    cache: dict[str, dict] = {}

    def _auth(role: str = Role.ADMIN.value) -> dict:
        if role not in cache:
            r = client.post("/api/v1/auth/login", json={"email": f"{role}@test.local", "password": PASSWORD})
            assert r.status_code == 200, r.text
            cache[role] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return cache[role]

    return _auth


@pytest.fixture()
def hospital(db):
    """Two departments with 3 beds each."""
    depts, beds = [], []
    for code in ("AAA", "BBB"):
        d = Department(name=f"Dept {code}", code=code, capacity=0)
        db.add(d)
        db.flush()
        depts.append(d)
        for i in range(1, 4):
            b = Bed(code=f"{code}-{i}", department_id=d.id, ward="W1")
            db.add(b)
            beds.append(b)
    db.commit()
    return {"depts": depts, "beds": beds}


@pytest.fixture()
def admitted_patient(client, auth, hospital):
    """Registers + admits a patient to dept AAA without a bed. Returns the patient JSON."""
    h = auth()
    p = client.post("/api/v1/patients", headers=h, json={"first_name": "Test", "last_name": "Patient", "date_of_birth": "1980-01-01"}).json()
    r = client.post(f"/api/v1/patients/{p['id']}/admit", headers=h, json={"department_id": hospital["depts"][0].id})
    assert r.status_code == 200, r.text
    return r.json()


def new_patient(client, headers, dept_id, bed_id=None, last="Patient"):
    p = client.post("/api/v1/patients", headers=headers, json={"first_name": "T", "last_name": last, "date_of_birth": "1990-05-05"}).json()
    r = client.post(f"/api/v1/patients/{p['id']}/admit", headers=headers, json={"department_id": dept_id, "bed_id": bed_id})
    assert r.status_code == 200, r.text
    return r.json()
