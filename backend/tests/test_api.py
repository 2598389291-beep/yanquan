"""API 集成测试（演示模式，无外部依赖）"""

SAMPLE_TEXT = (
    "我在拼多多买了一个蓝牙耳机花了99元，收到后发现是假货，"
    "和正品完全不一样，商家还不退款，我要退一赔三。"
)


def test_admin_quota_bypass_requires_auth(client, monkeypatch):
    """仅「已登录的白名单管理员」不限次数；未登录不能伪造管理员身份绕过"""
    from backend.config import settings
    from backend.database import create_or_update_user
    monkeypatch.setattr(settings, "admin_user_id", "1")

    user = create_or_update_user(phone="13800000000")
    token = user["token"]
    uid = str(user["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 已登录管理员：连发 11 次仍全部成功（不受 10 次限制）
    for _ in range(11):
        resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT, "user_id": uid}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    # usage 标记 unlimited
    resp = client.get(f"/api/usage?user_id={uid}", headers=headers)
    data = resp.json()["data"]
    assert data["unlimited"] is True

    # 未登录但伪造管理员 user_id：额度不放开（被拦截）
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT, "user_id": uid})
    assert resp.status_code == 403
    assert resp.json()["code"] == 4031


def test_email_login_flow(client):
    """邮箱登录：首次自动注册 → 错误密码拒绝 → 正确密码同一账号"""
    r = client.post("/api/auth/email/login", json={"email": "user@test.com", "password": "secret123"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["email"] == "user@test.com"
    assert data["token"]
    uid = data["user_id"]

    r = client.post("/api/auth/email/login", json={"email": "user@test.com", "password": "wrong-pass"})
    assert r.status_code == 401

    r = client.post("/api/auth/email/login", json={"email": "user@test.com", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["data"]["user_id"] == uid

    r = client.post("/api/auth/email/login", json={"email": "bad-email", "password": "secret123"})
    assert r.status_code == 400


# ---------- 基础 ----------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["mode"] == "demo"


def test_meta(client):
    resp = client.get("/api/meta")
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["app_name"] == "言权"
    assert data["data"]["demo_mode"] is True
    assert data["data"]["features"]["voice"] is False


# ---------- 投诉生成 ----------

def test_free_quota_per_user(client):
    """每个用户 10 次免费生成；用完后拦截；不同用户互不影响"""
    uid = "quota_user_a"
    for _ in range(10):
        resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT, "user_id": uid})
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    # 第 11 次被拦截（code=4031）
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT, "user_id": uid})
    assert resp.status_code == 403
    assert resp.json()["code"] == 4031
    assert "已用完" in resp.json()["detail"]

    # usage 接口
    resp = client.get(f"/api/usage?user_id={uid}")
    data = resp.json()["data"]
    assert data["total"] == 10
    assert data["used"] == 10
    assert data["remaining"] == 0

    # 其他用户额度独立
    resp = client.get("/api/usage?user_id=quota_user_b")
    assert resp.json()["data"]["used"] == 0
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT, "user_id": "quota_user_b"})
    assert resp.status_code == 200

def test_text_generate_full_flow(client):
    """文本生成 → 列表 → 详情 → 统计 → 状态流转 → 删除 全链路"""
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["id"] > 0
    assert "投诉信" in data["complaint_letter"]
    assert data["category"] in ("网购纠纷", "产品质量")
    assert len(data["legal_basis"]) >= 1
    assert len(data["action_path"]) >= 2
    assert data["channel_advice"]["channels"]
    assert data["negotiation_script"]["steps"]
    assert data["merchant_qualification_advice"]["items"]
    assert data["status"] == "generated"

    cid = data["id"]

    # 列表
    resp = client.get("/api/complaints")
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == cid

    # 详情
    resp = client.get(f"/api/complaint/{cid}")
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["complaint_letter"] == data["complaint_letter"]

    # 统计
    resp = client.get("/api/complaints/stats")
    stats = resp.json()["data"]
    assert stats["total"] == 1
    assert stats["categories"] >= 1

    # 状态流转
    resp = client.patch(f"/api/complaint/{cid}/status?status=copied")
    assert resp.json()["data"]["status"] == "copied"
    resp = client.patch(f"/api/complaint/{cid}/status?status=submitted")
    assert resp.json()["data"]["status_label"] == "已提交"

    # 无效状态
    resp = client.patch(f"/api/complaint/{cid}/status?status=invalid")
    assert resp.status_code == 400

    # 删除
    resp = client.delete(f"/api/complaint/{cid}")
    assert resp.json()["code"] == 0
    resp = client.get(f"/api/complaint/{cid}")
    assert resp.status_code == 404


def test_text_generate_other_user_isolation(client):
    """用户隔离：他人 user_id 不能操作不属于自己的记录"""
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT, "user_id": "user_a"})
    cid = resp.json()["data"]["id"]
    resp = client.patch(f"/api/complaint/{cid}/status?status=resolved&user_id=user_b")
    assert resp.status_code == 404
    resp = client.delete(f"/api/complaint/{cid}?user_id=user_b")
    assert resp.status_code == 404


def test_text_empty(client):
    resp = client.post("/api/complaint/text", json={"text": "   "})
    assert resp.status_code == 400


def test_order_info_merges(client):
    """订单信息传入后应出现在响应中"""
    resp = client.post(
        "/api/complaint/text",
        json={
            "text": "买的商品坏了，商家不给处理",
            "order_info": {
                "platform": "淘宝", "order_number": "20260801",
                "product_name": "无线鼠标", "amount": "129", "seller": "XX数码专营店",
            },
        },
    )
    data = resp.json()["data"]
    assert data["order_info"]["platform"] == "淘宝"
    assert "无线鼠标" in data["complaint_letter"]


# ---------- 认证 ----------

def test_phone_login(client):
    resp = client.post("/api/auth/send-code", json={"phone": "13800138000"})
    assert resp.json()["code"] == 0
    resp = client.post("/api/auth/verify", json={"phone": "13800138000", "code": "123456"})
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["token"]

    # 错误验证码
    resp = client.post("/api/auth/verify", json={"phone": "13800138000", "code": "000000"})
    assert resp.status_code == 400


def test_wechat_login_demo(client):
    resp = client.post(
        "/api/auth/wechat/login",
        json={"code": "demo-code-1", "nickname": "测试用户"},
    )
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["nickname"] == "测试用户"

    # 同一 code 应返回同一用户
    resp2 = client.post("/api/auth/wechat/login", json={"code": "demo-code-1"})
    assert resp2.json()["data"]["user_id"] == body["data"]["user_id"]


def test_bearer_token_authorization(client):
    """登录后带 token 调用，记录归属 token 对应用户"""
    client.post("/api/auth/send-code", json={"phone": "13900139000"})
    login = client.post("/api/auth/verify", json={"phone": "13900139000", "code": "123456"}).json()["data"]
    token = login["token"]

    resp = client.post(
        "/api/complaint/text",
        json={"text": SAMPLE_TEXT, "user_id": "evil_user"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cid = resp.json()["data"]["id"]

    # 用 token 查询列表应能看到
    resp = client.get("/api/complaints", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()["data"]["items"]) == 1

    # 删除接口带错误 user_id 但正确 token，仍应成功（以 token 为准）
    resp = client.delete(f"/api/complaint/{cid}?user_id=evil_user", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["code"] == 0


def test_validation_error(client):
    resp = client.post("/api/complaint/text", json={"bad": "field"})
    assert resp.status_code == 400


def test_status_update_post_body(client):
    """状态更新支持 POST + body（云调用兼容）"""
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT})
    cid = resp.json()["data"]["id"]
    resp = client.post(f"/api/complaint/{cid}/status", json={"status": "copied", "user_id": "default_user"})
    assert resp.json()["data"]["status"] == "copied"


def test_delete_post(client):
    """删除支持 POST /delete（云调用兼容）"""
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT})
    cid = resp.json()["data"]["id"]
    resp = client.post(f"/api/complaint/{cid}/delete", json={"user_id": "default_user"})
    assert resp.json()["code"] == 0
    assert client.get(f"/api/complaint/{cid}").status_code == 404
