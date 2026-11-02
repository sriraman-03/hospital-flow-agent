from sqlalchemy import select

from app.models.audit import AuditLog
from tests.conftest import new_patient


def test_register_validates_input(client, auth):
    h = auth()
    assert client.post("/api/v1/patients", headers=h, json={"first_name": " ", "last_name": "X", "date_of_birth": "1990-01-01"}).status_code == 422
    assert client.post("/api/v1/patients", headers=h, json={"first_name": "A", "last_name": "B", "date_of_birth": "2999-01-01"}).status_code == 422
    r = client.post("/api/v1/patients", headers=h, json={"first_name": "A", "last_name": "B", "date_of_birth": "1990-01-01"})
    assert r.status_code == 201
    assert r.json()["patient_code"].startswith("PT-")
    assert r.json()["status"] == "registered"


def test_list_search_filter_sort_paginate(client, auth, hospital):
    h = auth()
    for i in range(5):
        new_patient(client, h, hospital["depts"][0].id, last=f"Zed{i}")
    r = client.get("/api/v1/patients?page=1&page_size=2&sort=last_name&order=asc", headers=h).json()
    assert r["total"] == 5 and len(r["items"]) == 2 and r["pages"] == 3
    assert r["items"][0]["last_name"] == "Zed0"
    assert client.get("/api/v1/patients?q=Zed3", headers=h).json()["total"] == 1
    assert client.get("/api/v1/patients?status=registered", headers=h).json()["total"] == 0


def test_update_audit_has_field_names_not_values(client, auth, db, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    r = client.patch(f"/api/v1/patients/{p['id']}", headers=h, json={"last_name": "Renamed", "phone": "555-0100"})
    assert r.status_code == 200
    log = db.scalars(select(AuditLog).where(AuditLog.action == "patient.update")).one()
    assert sorted(log.details["fields_changed"]) == ["last_name", "phone"]
    assert "Renamed" not in str(log.details) and "555-0100" not in str(log.details)


def test_notifications_do_not_contain_patient_names(client, auth, hospital):
    h = auth()
    new_patient(client, h, hospital["depts"][0].id, last="Uniquename")
    items = client.get("/api/v1/notifications", headers=h).json()["items"]
    assert items
    assert all("Uniquename" not in (n["title"] + n["description"]) for n in items)


def test_admit_with_bed_and_history(client, auth, hospital):
    h = auth()
    bed = hospital["beds"][0]
    p = new_patient(client, h, hospital["depts"][0].id, bed.id)
    assert p["bed_code"] == bed.code and p["status"] == "admitted"
    hist = client.get(f"/api/v1/patients/{p['id']}/history", headers=h).json()
    assert {e["type"] for e in hist} >= {"registration", "bed_assigned"}


def test_cannot_admit_twice(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    r = client.post(f"/api/v1/patients/{p['id']}/admit", headers=h, json={"department_id": hospital["depts"][1].id})
    assert r.status_code == 409
