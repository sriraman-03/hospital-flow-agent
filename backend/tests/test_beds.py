import threading

import pytest

from app.core.errors import ConflictError
from app.db.session import SessionLocal
from app.models.hospital import BedAssignment
from app.models.user import User
from app.services import bed_service
from sqlalchemy import select
from tests.conftest import new_patient


def test_assign_and_conflicts(client, auth, hospital):
    h = auth()
    d0, bed = hospital["depts"][0], hospital["beds"][0]
    p1 = new_patient(client, h, d0.id)
    p2 = new_patient(client, h, d0.id, last="Second")
    assert client.post(f"/api/v1/beds/{bed.id}/assign", headers=h, json={"patient_id": p1["id"]}).status_code == 200
    # bed already taken
    assert client.post(f"/api/v1/beds/{bed.id}/assign", headers=h, json={"patient_id": p2["id"]}).status_code == 409
    # patient already has a bed
    other = hospital["beds"][1]
    assert client.post(f"/api/v1/beds/{other.id}/assign", headers=h, json={"patient_id": p1["id"]}).status_code == 409


def test_unavailable_bed_cannot_be_assigned(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    bed = hospital["beds"][0]
    assert client.patch(f"/api/v1/beds/{bed.id}/status", headers=h, json={"status": "maintenance"}).status_code == 200
    assert client.post(f"/api/v1/beds/{bed.id}/assign", headers=h, json={"patient_id": p["id"]}).status_code == 409


def test_bed_in_other_department_rejected(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    foreign = hospital["beds"][3]
    assert client.post(f"/api/v1/beds/{foreign.id}/assign", headers=h, json={"patient_id": p["id"]}).status_code == 409


def test_cannot_manually_set_occupied(client, auth, hospital):
    r = client.patch(f"/api/v1/beds/{hospital['beds'][0].id}/status", headers=auth(), json={"status": "occupied"})
    assert r.status_code == 422


def test_move_between_beds_is_atomic(client, auth, hospital):
    h = auth()
    b1, b2 = hospital["beds"][0], hospital["beds"][1]
    p = new_patient(client, h, hospital["depts"][0].id, b1.id)
    assert client.post("/api/v1/beds/transfer-bed", headers=h, json={"patient_id": p["id"], "to_bed_id": b2.id}).status_code == 200
    beds = {b["code"]: b for b in client.get("/api/v1/beds", headers=h).json()["items"]}
    assert beds[b1.code]["status"] == "cleaning" and beds[b2.code]["status"] == "occupied"
    hist = client.get(f"/api/v1/beds/assignments?patient_id={p['id']}", headers=h).json()
    assert hist["total"] == 2


def test_failed_move_leaves_original_assignment(client, auth, hospital):
    h = auth()
    b1, b2 = hospital["beds"][0], hospital["beds"][1]
    p = new_patient(client, h, hospital["depts"][0].id, b1.id)
    client.patch(f"/api/v1/beds/{b2.id}/status", headers=h, json={"status": "maintenance"})
    assert client.post("/api/v1/beds/transfer-bed", headers=h, json={"patient_id": p["id"], "to_bed_id": b2.id}).status_code == 409
    got = client.get(f"/api/v1/patients/{p['id']}", headers=h).json()
    assert got["bed_code"] == b1.code  # rolled back


def test_release_sets_cleaning(client, auth, hospital):
    h = auth()
    bed = hospital["beds"][0]
    new_patient(client, h, hospital["depts"][0].id, bed.id)
    r = client.post(f"/api/v1/beds/{bed.id}/release", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cleaning"


def test_concurrent_allocation_never_double_books(client, auth, hospital, db):
    h = auth()
    bed = hospital["beds"][0]
    ids = [new_patient(client, h, hospital["depts"][0].id, last=f"C{i}")["id"] for i in range(6)]
    actor_id = db.scalar(select(User.id))
    results: list[str] = []
    barrier = threading.Barrier(len(ids))

    def worker(pid: int):
        s = SessionLocal()
        try:
            actor = s.get(User, actor_id)
            barrier.wait()
            bed_service.assign_bed(s, actor, bed.id, pid)
            results.append("ok")
        except ConflictError:
            results.append("conflict")
        except Exception as exc:  # e.g. SQLite lock timeouts also mean "not allocated"
            results.append(f"error:{type(exc).__name__}")
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(pid,)) for pid in ids]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count("ok") == 1, results
    active = db.scalars(select(BedAssignment).where(BedAssignment.bed_id == bed.id, BedAssignment.released_at.is_(None))).all()
    assert len(active) == 1
