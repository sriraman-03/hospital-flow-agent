from sqlalchemy import select

from app.models.audit import AIWorkflowExecution
from tests.conftest import new_patient
from tests.test_resources import make, mv


def test_dashboard_numbers_come_from_database(client, auth, hospital):
    h = auth()
    s0 = client.get("/api/v1/dashboard/summary", headers=h).json()
    assert s0["total_patients"] == 0 and s0["available_beds"] == 6 and s0["occupancy_rate"] == 0
    new_patient(client, h, hospital["depts"][0].id, hospital["beds"][0].id)
    r = make(client, h, quantity=3, min_threshold=10, critical_threshold=5)
    s = client.get("/api/v1/dashboard/summary", headers=h).json()
    assert s["total_patients"] == 1 and s["admitted_patients"] == 1
    assert s["occupied_beds"] == 1 and s["available_beds"] == 5 and s["occupancy_rate"] == round(100 / 6, 1)
    assert s["low_stock_resources"] == 1 and s["critical_active_alerts"] == 1 and s["unread_notifications"] >= 1
    a = client.get("/api/v1/dashboard/analytics?days=7", headers=h).json()
    assert len(a["admissions_vs_discharges"]) == 7
    assert sum(d["admissions"] for d in a["admissions_vs_discharges"]) == 1
    assert {x["severity"] for x in a["alerts_by_severity"]} == {"critical", "warning", "info", "success"}
    assert a["critical_alerts"] and a["recent_activity"]


def test_capacity_alert_when_occupancy_high(client, auth, hospital):
    h = auth()
    for i, b in enumerate(hospital["beds"][:3]):
        new_patient(client, h, hospital["depts"][0].id, b.id, last=f"Full{i}")
    items = client.get("/api/v1/notifications?category=bed&severity=critical", headers=h).json()["items"]
    assert any("critical bed occupancy" in n["title"] for n in items)


def test_ai_assistant_works_without_llm(client, auth, hospital, db):
    h = auth()
    r = make(client, h, quantity=2, min_threshold=10, critical_threshold=5)
    res = client.post("/api/v1/ai/workflows/run", headers=h, json={"workflow": "operations_summary"})
    assert res.status_code == 200
    body = res.json()
    assert body["used_llm"] is False and body["ai_narrative"] is None
    assert "summary" in body["facts"] and "disclaimer" in body
    low = client.post("/api/v1/ai/workflows/run", headers=h, json={"workflow": "low_stock"}).json()
    assert any(f["resource_id"] == r["id"] for f in low["facts"]["low_stock"])
    assert db.scalars(select(AIWorkflowExecution).where(AIWorkflowExecution.status == "completed")).all()
    ask = client.post("/api/v1/ai/workflows/run", headers=h, json={"workflow": "ask", "question": "Which supplies are running low?"}).json()
    assert ask["workflow"] == "low_stock"


def test_ai_failures_are_recorded(client, auth, db):
    h = auth()
    r = client.post("/api/v1/ai/workflows/run", headers=h, json={"workflow": "explain_routing"})  # missing patient_id
    assert r.status_code == 422
    assert db.scalars(select(AIWorkflowExecution).where(AIWorkflowExecution.status == "failed")).all()
    assert client.post("/api/v1/ai/workflows/run", headers=h, json={"workflow": "nope"}).status_code == 422


def test_ai_requires_permission(client, auth):
    for role in ("viewer", "department_staff"):
        assert client.post("/api/v1/ai/workflows/run", headers=auth(role), json={"workflow": "operations_summary"}).status_code == 403
    assert client.post("/api/v1/ai/workflows/run", headers=auth("operations_staff"), json={"workflow": "operations_summary"}).status_code == 200


def test_audit_log_records_actor_and_excludes_secrets(client, auth, hospital):
    h = auth()
    new_patient(client, h, hospital["depts"][0].id, hospital["beds"][0].id)
    client.post("/api/v1/users", headers=h, json={"email": "n@test.local", "full_name": "N", "password": "Another-Pass-123", "role": "viewer"})
    logs = client.get("/api/v1/audit-logs?page_size=100", headers=h).json()["items"]
    actions = {l["action"] for l in logs}
    assert {"patient.register", "patient.admit", "bed.assigned", "user.create", "auth.login"} <= actions
    dump = str(logs)
    assert "Another-Pass-123" not in dump and "hashed_password" not in dump and "Bearer" not in dump
    assert all(l["actor_email"] for l in logs if l["action"] == "patient.register")


def test_settings_validation(client, auth):
    h = auth()
    assert client.put("/api/v1/settings", headers=h, json={"values": {"bogus": 1}}).status_code == 422
    assert client.put("/api/v1/settings", headers=h, json={"values": {"occupancy_warning_pct": 99}}).status_code == 422
    assert client.get("/api/v1/settings", headers=auth("viewer")).status_code == 200
    assert client.put("/api/v1/settings", headers=auth("operations_staff"), json={"values": {}}).status_code == 403


def test_user_cannot_deactivate_self(client, auth, users):
    me = users["administrator"]
    r = client.patch(f"/api/v1/users/{me.id}", headers=auth(), json={"is_active": False})
    assert r.status_code == 403
