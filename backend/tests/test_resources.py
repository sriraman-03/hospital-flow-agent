from sqlalchemy import select

from app.models.notification import Notification


def make(client, h, **kw):
    body = {"name": "Gloves", "category": "PPE", "unit": "boxes", "quantity": 100, "min_threshold": 50, "critical_threshold": 20,
            "storage_location": "Main"} | kw
    r = client.post("/api/v1/resources", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def mv(client, h, rid, typ, qty, reason=None):
    return client.post(f"/api/v1/resources/{rid}/movements", headers=h, json={"movement_type": typ, "quantity": qty, "reason": reason})


def test_negative_stock_prevented(client, auth):
    h = auth()
    r = make(client, h)
    assert mv(client, h, r["id"], "deduction", 101).status_code == 409
    assert client.get(f"/api/v1/resources/{r['id']}", headers=h).json()["quantity"] == 100
    assert mv(client, h, r["id"], "deduction", 0).status_code == 422
    assert mv(client, h, r["id"], "adjustment", 5).status_code == 422  # reason required


def test_threshold_validation(client, auth):
    h = auth()
    r = client.post("/api/v1/resources", headers=h, json={"name": "X", "quantity": 1, "min_threshold": 5, "critical_threshold": 10})
    assert r.status_code == 422


def test_movement_history(client, auth):
    h = auth()
    r = make(client, h)
    mv(client, h, r["id"], "deduction", 30)
    mv(client, h, r["id"], "addition", 10)
    hist = client.get(f"/api/v1/resources/{r['id']}/movements", headers=h).json()
    assert hist["total"] == 3  # initial + 2
    assert hist["items"][0]["quantity_after"] == 80


def test_low_alert_deduplicated_then_escalates_and_recovers(client, auth, db):
    h = auth()
    r = make(client, h)
    mv(client, h, r["id"], "deduction", 55)  # 45 -> low
    mv(client, h, r["id"], "deduction", 1)   # 44 -> still low: NO duplicate
    low = db.scalars(select(Notification).where(Notification.dedup_key == f"resource:{r['id']}:low")).all()
    assert len(low) == 1 and low[0].severity == "warning" and not low[0].is_resolved

    mv(client, h, r["id"], "deduction", 30)  # 14 -> critical, low auto-resolved
    db.expire_all()
    crit = db.scalars(select(Notification).where(Notification.dedup_key == f"resource:{r['id']}:critical")).all()
    assert len(crit) == 1 and crit[0].severity == "critical"
    assert db.scalars(select(Notification).where(Notification.dedup_key == f"resource:{r['id']}:low")).one().is_resolved

    mv(client, h, r["id"], "addition", 200)  # recovered
    db.expire_all()
    assert db.scalars(select(Notification).where(Notification.dedup_key == f"resource:{r['id']}:critical")).one().is_resolved
    assert db.scalars(select(Notification).where(Notification.category == "resource", Notification.severity == "success")).all()


def test_editing_thresholds_reevaluates(client, auth, db):
    h = auth()
    r = make(client, h, quantity=60)  # ok
    assert client.patch(f"/api/v1/resources/{r['id']}", headers=h, json={"min_threshold": 80, "critical_threshold": 10}).status_code == 200
    assert db.scalars(select(Notification).where(Notification.dedup_key == f"resource:{r['id']}:low")).one()


def test_quantity_cannot_be_patched_directly(client, auth):
    h = auth()
    r = make(client, h)
    assert client.patch(f"/api/v1/resources/{r['id']}", headers=h, json={"quantity": 5}).status_code in (200, 422)
    assert client.get(f"/api/v1/resources/{r['id']}", headers=h).json()["quantity"] == 100
