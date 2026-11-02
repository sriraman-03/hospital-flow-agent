from sqlalchemy import select

from app.models.hospital import BedAssignment
from tests.conftest import new_patient


def mk(client, h, patient_id, dest_id, bed_id=None):
    return client.post("/api/v1/transfers", headers=h, json={"patient_id": patient_id, "destination_department_id": dest_id,
                                                           "destination_bed_id": bed_id, "reason": "capacity"})


def test_full_lifecycle_moves_patient_and_beds(client, auth, hospital, db):
    h = auth()
    src_bed, dst_bed = hospital["beds"][0], hospital["beds"][3]
    p = new_patient(client, h, hospital["depts"][0].id, src_bed.id)
    t = mk(client, h, p["id"], hospital["depts"][1].id, dst_bed.id)
    assert t.status_code == 201 and t.json()["status"] == "requested"
    tid = t.json()["id"]
    assert client.post(f"/api/v1/transfers/{tid}/start", headers=h).status_code == 409   # not approved yet
    assert client.post(f"/api/v1/transfers/{tid}/complete", headers=h).status_code == 409
    assert client.post(f"/api/v1/transfers/{tid}/approve", headers=h).json()["status"] == "approved"
    assert client.post(f"/api/v1/transfers/{tid}/approve", headers=h).status_code == 409  # cannot re-approve
    assert client.post(f"/api/v1/transfers/{tid}/start", headers=h).json()["status"] == "in_progress"
    done = client.post(f"/api/v1/transfers/{tid}/complete", headers=h).json()
    assert done["status"] == "completed" and done["completed_at"]

    got = client.get(f"/api/v1/patients/{p['id']}", headers=h).json()
    assert got["department_id"] == hospital["depts"][1].id and got["bed_code"] == dst_bed.code
    beds = {b["code"]: b["status"] for b in client.get("/api/v1/beds", headers=h).json()["items"]}
    assert beds[src_bed.code] == "cleaning" and beds[dst_bed.code] == "occupied"
    active = db.scalars(select(BedAssignment).where(BedAssignment.patient_id == p["id"], BedAssignment.released_at.is_(None))).all()
    assert len(active) == 1


def test_cancel_requires_reason_and_is_terminal(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    tid = mk(client, h, p["id"], hospital["depts"][1].id).json()["id"]
    assert client.post(f"/api/v1/transfers/{tid}/cancel", headers=h, json={"reason": ""}).status_code == 422
    r = client.post(f"/api/v1/transfers/{tid}/cancel", headers=h, json={"reason": "Patient stable, no longer needed"})
    assert r.json()["status"] == "cancelled" and r.json()["cancellation_reason"]
    assert client.post(f"/api/v1/transfers/{tid}/approve", headers=h).status_code == 409


def test_one_open_transfer_per_patient_and_same_dept_rejected(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    assert mk(client, h, p["id"], hospital["depts"][0].id).status_code == 422
    assert mk(client, h, p["id"], hospital["depts"][1].id).status_code == 201
    assert mk(client, h, p["id"], hospital["depts"][1].id).status_code == 409


def test_destination_bed_must_be_available_and_in_destination(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    assert mk(client, h, p["id"], hospital["depts"][1].id, hospital["beds"][1].id).status_code == 422  # wrong dept
    client.patch(f"/api/v1/beds/{hospital['beds'][3].id}/status", headers=h, json={"status": "maintenance"})
    assert mk(client, h, p["id"], hospital["depts"][1].id, hospital["beds"][3].id).status_code == 409


def test_complete_rolls_back_if_destination_bed_taken(client, auth, hospital):
    h = auth()
    src, dst = hospital["beds"][0], hospital["beds"][3]
    p = new_patient(client, h, hospital["depts"][0].id, src.id)
    tid = mk(client, h, p["id"], hospital["depts"][1].id, dst.id).json()["id"]
    client.post(f"/api/v1/transfers/{tid}/approve", headers=h)
    client.post(f"/api/v1/transfers/{tid}/start", headers=h)
    other = new_patient(client, h, hospital["depts"][1].id, dst.id, last="Taker")  # someone takes the bed meanwhile
    assert other["bed_code"] == dst.code
    assert client.post(f"/api/v1/transfers/{tid}/complete", headers=h).status_code == 409
    got = client.get(f"/api/v1/patients/{p['id']}", headers=h).json()
    assert got["department_id"] == hospital["depts"][0].id and got["bed_code"] == src.code  # nothing half-applied
    assert client.get(f"/api/v1/transfers/{tid}", headers=h).json()["status"] == "in_progress"


def test_department_staff_can_request_but_not_approve(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    ds = auth("department_staff")
    tid = mk(client, ds, p["id"], hospital["depts"][1].id).json()["id"]
    assert client.post(f"/api/v1/transfers/{tid}/approve", headers=ds).status_code == 403
    assert client.post(f"/api/v1/transfers/{tid}/approve", headers=auth("operations_staff")).status_code == 200


def test_routing_recommendation_and_confirmation(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    rec = client.post("/api/v1/routing/recommendations", headers=h, json={"patient_id": p["id"]}).json()
    by = {c["department_name"]: c for c in rec["candidates"]}
    assert by["Dept AAA"]["eligible"] is False and "already in this department" in by["Dept AAA"]["blockers"][0]
    assert by["Dept BBB"]["eligible"] and by["Dept BBB"]["reasons"]
    assert "clinical" in rec["disclaimer"].lower()
    # nothing changed until confirmed
    assert client.get("/api/v1/transfers", headers=h).json()["total"] == 0
    c = client.post("/api/v1/routing/confirm", headers=h, json={"patient_id": p["id"], "department_id": hospital["depts"][1].id})
    assert c.json()["action"] == "transfer_requested"
    # ineligible choice is refused
    bad = client.post("/api/v1/routing/confirm", headers=h, json={"patient_id": p["id"], "department_id": hospital["depts"][0].id})
    assert bad.status_code == 409


def test_routing_blocks_when_no_beds(client, auth, hospital):
    h = auth()
    for b in hospital["beds"][3:]:
        client.patch(f"/api/v1/beds/{b.id}/status", headers=h, json={"status": "maintenance"})
    p = new_patient(client, h, hospital["depts"][0].id)
    rec = client.post("/api/v1/routing/recommendations", headers=h, json={"patient_id": p["id"]}).json()
    bbb = next(c for c in rec["candidates"] if c["department_name"] == "Dept BBB")
    assert not bbb["eligible"] and "No available beds" in bbb["blockers"]
