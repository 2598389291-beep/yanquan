"""客服运营端 RBAC、案件流转与操作日志测试。"""

from backend import database as db


def _create_user(phone: str, role: str = "consumer") -> dict:
    user = db.create_or_update_user(phone=phone)
    if role != "consumer":
        user = db.set_user_role(str(user["id"]), role)
    return user


def _headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {user['token']}"}


def _create_case(user_id: str) -> dict:
    return db.save_complaint(
        user_id=user_id,
        raw_text="商家拒绝退款，要求平台介入处理",
        complaint_letter="投诉信正文",
        legal_basis=["消费者权益保护法-39"],
        action_path=["联系平台"],
        category="网购纠纷",
    )


def test_case_has_sla_due_at_and_summary_counts(client):
    consumer = _create_user("13800000023")
    admin = _create_user("13800000024", "admin")
    case = _create_case(str(consumer["id"]))
    assert case["sla_due_at"]

    summary = client.get("/api/operations/summary", headers=_headers(admin))
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["total"] == 1
    assert data["pending_assignment"] == 1
    assert data["overdue"] == 0

    conn = db.get_connection()
    conn.execute(
        "UPDATE complaints SET sla_due_at = datetime('now','localtime','-1 hour') WHERE id = ?",
        (case["id"],),
    )
    conn.commit()
    conn.close()

    detail = client.get(f"/api/operations/cases/{case['id']}", headers=_headers(admin))
    assert detail.json()["data"]["sla_state"] == "overdue"
    summary = client.get("/api/operations/summary", headers=_headers(admin))
    assert summary.json()["data"]["overdue"] == 1


def test_login_exposes_consumer_role(client):
    resp = client.post(
        "/api/auth/email/login",
        json={"email": "role-check@test.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "consumer"


def test_configured_admin_login_exposes_admin_role(client, monkeypatch):
    from backend.config import settings

    user = _create_user("13800000019")
    monkeypatch.setattr(settings, "admin_user_id", str(user["id"]))
    resp = client.post(
        "/api/auth/email/login",
        json={"email": "admin-role@test.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "consumer"

    client.post("/api/auth/send-code", json={"phone": "13800000019"})
    login = client.post(
        "/api/auth/verify",
        json={"phone": "13800000019", "code": "123456"},
    )
    assert login.status_code == 200
    assert login.json()["data"]["role"] == "admin"


def test_operations_requires_staff_role(client):
    consumer = _create_user("13800000001")
    assert client.get("/api/operations/cases").status_code == 401
    resp = client.get("/api/operations/cases", headers=_headers(consumer))
    assert resp.status_code == 403


def test_admin_can_promote_user_to_agent(client):
    consumer = _create_user("13800000020")
    admin = _create_user("13800000021", "admin")

    denied = client.post(
        f"/api/operations/users/{consumer['id']}/role",
        json={"role": "agent"},
        headers=_headers(consumer),
    )
    assert denied.status_code == 403

    promoted = client.post(
        f"/api/operations/users/{consumer['id']}/role",
        json={"role": "agent"},
        headers=_headers(admin),
    )
    assert promoted.status_code == 200
    assert promoted.json()["data"]["role"] == "agent"
    assert client.get("/api/operations/cases", headers=_headers(consumer)).status_code == 200


def test_configured_admin_appears_in_assignment_list(client, monkeypatch):
    from backend.config import settings

    admin = _create_user("13800000022")
    monkeypatch.setattr(settings, "admin_user_id", str(admin["id"]))
    resp = client.get("/api/operations/agents", headers=_headers(admin))
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert any(item["id"] == admin["id"] and item["role"] == "admin" for item in items)


def test_admin_assigns_case_and_agent_sees_only_own_queue(client):
    consumer = _create_user("13800000002")
    admin = _create_user("13800000003", "admin")
    agent = _create_user("13800000004", "agent")
    other_agent = _create_user("13800000005", "agent")
    case = _create_case(str(consumer["id"]))

    unassigned = client.get("/api/operations/cases", headers=_headers(agent))
    assert unassigned.status_code == 200
    assert unassigned.json()["data"]["items"][0]["id"] == case["id"]

    resp = client.post(
        f"/api/operations/cases/{case['id']}/assign",
        json={"assignee_id": str(agent["id"])},
        headers=_headers(admin),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["assignee_id"] == str(agent["id"])
    assert data["assignee_name"] == agent["phone"]
    assert data["case_status"] == "in_progress"
    assert data["events"][-1]["action"] == "assigned"

    visible = client.get("/api/operations/cases", headers=_headers(agent)).json()["data"]["items"]
    assert [item["id"] for item in visible] == [case["id"]]

    hidden = client.get("/api/operations/cases", headers=_headers(other_agent)).json()["data"]["items"]
    assert hidden == []

    detail = client.get(
        f"/api/operations/cases/{case['id']}",
        headers=_headers(other_agent),
    )
    assert detail.status_code == 403


def test_agent_cannot_steal_assigned_case(client):
    consumer = _create_user("13800000006")
    agent_a = _create_user("13800000007", "agent")
    agent_b = _create_user("13800000008", "agent")
    case = _create_case(str(consumer["id"]))

    first = client.post(
        f"/api/operations/cases/{case['id']}/claim",
        headers=_headers(agent_a),
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/operations/cases/{case['id']}/claim",
        headers=_headers(agent_b),
    )
    assert second.status_code == 409


def test_case_status_machine_and_operation_log(client):
    consumer = _create_user("13800000009")
    agent = _create_user("13800000010", "agent")
    case = _create_case(str(consumer["id"]))

    client.post(
        f"/api/operations/cases/{case['id']}/claim",
        headers=_headers(agent),
    )
    invalid = client.post(
        f"/api/operations/cases/{case['id']}/status",
        json={"case_status": "pending_assignment"},
        headers=_headers(agent),
    )
    assert invalid.status_code == 400

    resp = client.post(
        f"/api/operations/cases/{case['id']}/status",
        json={"case_status": "waiting_user"},
        headers=_headers(agent),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["case_status"] == "waiting_user"

    resp = client.post(
        f"/api/operations/cases/{case['id']}/status",
        json={"case_status": "resolved"},
        headers=_headers(agent),
    )
    assert resp.status_code == 200
    actions = [event["action"] for event in resp.json()["data"]["events"]]
    assert actions == ["claimed", "status_changed", "status_changed"]


def test_user_progress_only_visible_to_owner(client):
    owner = _create_user("13800000011")
    stranger = _create_user("13800000012")
    agent = _create_user("13800000013", "agent")
    case = _create_case(str(owner["id"]))
    client.post(
        f"/api/operations/cases/{case['id']}/claim",
        headers=_headers(agent),
    )

    resp = client.get(
        f"/api/complaint/{case['id']}/progress",
        headers=_headers(owner),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["case_status"] == "in_progress"
    assert resp.json()["data"]["assignee_name"] == "客服人员"
    assert resp.json()["data"]["sla_due_at"]
    assert resp.json()["data"]["events"][0]["label"] == "客服已认领"

    denied = client.get(
        f"/api/complaint/{case['id']}/progress",
        headers=_headers(stranger),
    )
    assert denied.status_code == 404
