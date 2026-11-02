from tests.conftest import new_patient


def test_discharge_flow_releases_bed_consistently(client, auth, hospital):
    h = auth()
    bed = hospital["beds"][0]
    p = new_patient(client, h, hospital["depts"][0].id, bed.id)
    d = client.post("/api/v1/discharges", headers=h, json={"patient_id": p["id"], "notes": "Home"})
    assert d.status_code == 201 and d.json()["status"] == "requested"
    did = d.json()["id"]
    assert client.get(f"/api/v1/patients/{p['id']}", headers=h).json()["status"] == "discharge_pending"
    assert client.post(f"/api/v1/discharges/{did}/complete", headers=h).status_code == 409  # approval first
    assert client.post(f"/api/v1/discharges/{did}/approve", headers=h).json()["status"] == "approved"
    done = client.post(f"/api/v1/discharges/{did}/complete", headers=h).json()
    assert done["status"] == "completed"
    patient = client.get(f"/api/v1/patients/{p['id']}", headers=h).json()
    assert patient["status"] == "discharged" and patient["discharged_at"] and patient["bed_code"] is None
    beds = {b["code"]: b["status"] for b in client.get("/api/v1/beds", headers=h).json()["items"]}
    assert beds[bed.code] == "cleaning"
    assert client.post(f"/api/v1/discharges/{did}/complete", headers=h).status_code == 409


def test_cancel_returns_patient_to_admitted(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    did = client.post("/api/v1/discharges", headers=h, json={"patient_id": p["id"]}).json()["id"]
    assert client.post(f"/api/v1/discharges/{did}/cancel", headers=h, json={"reason": ""}).status_code == 422
    assert client.post(f"/api/v1/discharges/{did}/cancel", headers=h, json={"reason": "Not ready"}).json()["status"] == "cancelled"
    assert client.get(f"/api/v1/patients/{p['id']}", headers=h).json()["status"] == "admitted"


def test_duplicate_open_discharge_and_non_admitted_rejected(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    assert client.post("/api/v1/discharges", headers=h, json={"patient_id": p["id"]}).status_code == 201
    assert client.post("/api/v1/discharges", headers=h, json={"patient_id": p["id"]}).status_code == 409
    reg = client.post("/api/v1/patients", headers=h, json={"first_name": "R", "last_name": "G", "date_of_birth": "1990-01-01"}).json()
    assert client.post("/api/v1/discharges", headers=h, json={"patient_id": reg["id"]}).status_code == 409


def test_setting_can_disable_approval_requirement(client, auth, hospital):
    h = auth()
    assert client.put("/api/v1/settings", headers=h, json={"values": {"discharge_requires_approval": False}}).status_code == 200
    p = new_patient(client, h, hospital["depts"][0].id)
    d = client.post("/api/v1/discharges", headers=h, json={"patient_id": p["id"]}).json()
    assert d["status"] == "approved"


def test_only_approvers_can_approve_discharge(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    did = client.post("/api/v1/discharges", headers=auth("department_staff"), json={"patient_id": p["id"]}).json()["id"]
    assert client.post(f"/api/v1/discharges/{did}/approve", headers=auth("department_staff")).status_code == 403
    assert client.post(f"/api/v1/discharges/{did}/approve", headers=auth("operations_staff")).status_code == 200


def test_open_transfer_blocks_discharge(client, auth, hospital):
    h = auth()
    p = new_patient(client, h, hospital["depts"][0].id)
    client.post("/api/v1/transfers", headers=h, json={"patient_id": p["id"], "destination_department_id": hospital["depts"][1].id})
    assert client.post("/api/v1/discharges", headers=h, json={"patient_id": p["id"]}).status_code == 409
