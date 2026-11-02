from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.enums import NotificationCategory, NotificationSeverity
from app.services import notification_service as ns
from tests.test_resources import make, mv


def seed_alert(client, h):
    r = make(client, h)
    mv(client, h, r["id"], "deduction", 85)  # critical
    return r


def first(client, h, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(f"/api/v1/notifications?{q}", headers=h).json()


def test_list_newest_first_and_filters(client, auth):
    h = auth()
    seed_alert(client, h)
    data = first(client, h)
    stamps = [n["created_at"] for n in data["items"]]
    assert stamps == sorted(stamps, reverse=True)
    assert first(client, h, severity="critical")["total"] == 1
    assert first(client, h, category="resource")["total"] >= 1
    assert first(client, h, category="bed")["total"] == 0
    assert first(client, h, q="Critical")["total"] == 1
    assert first(client, h, is_resolved="false")["total"] >= 1
    assert first(client, h, date_from="2999-01-01T00:00:00")["total"] == 0


def test_read_unread_and_counts(client, auth):
    h = auth()
    seed_alert(client, h)
    before = client.get("/api/v1/notifications/unread-count", headers=h).json()
    assert before["unread"] >= 1 and before["critical_active"] == 1
    nid = first(client, h, severity="critical")["items"][0]["id"]
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=h).json()["is_read"] is True
    assert client.get("/api/v1/notifications/unread-count", headers=h).json()["unread"] == before["unread"] - 1
    assert client.post(f"/api/v1/notifications/{nid}/unread", headers=h).json()["is_read"] is False
    assert client.post("/api/v1/notifications/read-all", headers=h).status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=h).json()["unread"] == 0


def test_read_is_not_resolved(client, auth):
    h = auth()
    seed_alert(client, h)
    nid = first(client, h, severity="critical")["items"][0]["id"]
    n = client.post(f"/api/v1/notifications/{nid}/read", headers=h).json()
    assert n["is_read"] and not n["is_resolved"]
    assert client.get("/api/v1/notifications/unread-count", headers=h).json()["critical_active"] == 1


def test_acknowledge_and_resolve_audited(client, auth, db):
    h = auth()
    seed_alert(client, h)
    nid = first(client, h, severity="critical")["items"][0]["id"]
    ack = client.post(f"/api/v1/notifications/{nid}/acknowledge", headers=h).json()
    assert ack["is_acknowledged"] and not ack["is_resolved"]
    res = client.post(f"/api/v1/notifications/{nid}/resolve", headers=h, json={"note": "Restock ordered"}).json()
    assert res["is_resolved"] and res["resolution_note"] == "Restock ordered"
    assert client.post(f"/api/v1/notifications/{nid}/resolve", headers=h, json={}).status_code == 409
    assert client.post(f"/api/v1/notifications/{nid}/acknowledge", headers=h).status_code == 409
    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {"notification.acknowledge", "notification.resolve"} <= actions
    assert client.get("/api/v1/notifications/unread-count", headers=h).json()["critical_active"] == 0


def test_viewer_can_read_but_not_manage(client, auth):
    h = auth()
    seed_alert(client, h)
    v = auth("viewer")
    nid = first(client, v)["items"][0]["id"]
    assert client.get("/api/v1/notifications/unread-count", headers=v).status_code == 200
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=v).status_code == 403
    assert client.post(f"/api/v1/notifications/{nid}/resolve", headers=v, json={}).status_code == 403


def test_event_key_idempotency_and_dedup_key(db):
    kw = dict(title="t", description="d", category=NotificationCategory.SYSTEM, severity=NotificationSeverity.INFO)
    a = ns.create_notification(db, event_key="evt:1", **kw)
    b = ns.create_notification(db, event_key="evt:1", **kw)
    assert a.id == b.id
    c = ns.create_notification(db, dedup_key="cond:1", **kw)
    d = ns.create_notification(db, dedup_key="cond:1", **kw)
    assert c.id == d.id
    c.is_resolved = True
    db.flush()
    e = ns.create_notification(db, dedup_key="cond:1", **kw)  # condition recurred after resolution -> new alert
    assert e.id != c.id
    db.commit()


def test_pagination(client, auth):
    h = auth()
    for i in range(3):
        make(client, h, name=f"Item{i}", quantity=1, min_threshold=5, critical_threshold=2)
    page = first(client, h, page=1, page_size=2)
    assert len(page["items"]) == 2 and page["total"] >= 3 and page["pages"] >= 2
