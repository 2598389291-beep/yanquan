"""新功能测试：法律溯源 / 证据包 / 维权指南 / 反馈"""

import io

SAMPLE_TEXT = (
    "我在拼多多买了一个蓝牙耳机花了99元，收到后发现是假货，"
    "和正品完全不一样，商家还不退款，我要退一赔三。"
)


def _make_complaint(client) -> int:
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT})
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


# ---------- 法律溯源 ----------

def test_generate_returns_legal_details(client):
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT})
    data = resp.json()["data"]
    assert data["legal_details"], "生成结果应包含 legal_details"
    detail = data["legal_details"][0]
    assert detail["law_name"]
    assert detail["article"]
    assert detail["content"]
    assert "flk.npc.gov.cn" in detail["source_url"]


def test_laws_list(client):
    resp = client.get("/api/laws")
    body = resp.json()
    assert body["code"] == 0
    laws = body["data"]["laws"]
    assert len(laws) >= 20
    assert any("消费者权益保护法" == l["law_name"] and "55" in l["article"] for l in laws)
    assert all(l.get("source_url") for l in laws)


def test_law_stats(client):
    resp = client.get("/api/laws/stats")
    assert resp.json()["data"]["total"] >= 20


# ---------- 维权指南 ----------

def test_guide_scenarios(client):
    resp = client.get("/api/guide/scenarios")
    scenarios = resp.json()["data"]["scenarios"]
    assert len(scenarios) == 8
    s = scenarios[0]
    assert s["key"] and s["title"] and s["steps"] and s["laws"] and s["tips"]


def test_guide_scenario_detail(client):
    resp = client.get("/api/guide/scenarios/fake_goods")
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["title"] == "网购假货 / 货不对板"
    resp = client.get("/api/guide/scenarios/not_exist")
    assert resp.status_code == 404


# ---------- 反馈 ----------

def test_feedback_flow(client):
    cid = _make_complaint(client)
    resp = client.post("/api/feedback", json={"complaint_id": cid, "rating": "helpful"})
    assert resp.json()["code"] == 0
    resp = client.post("/api/feedback", json={"complaint_id": cid, "rating": "unhelpful", "comment": "法条引用不够准确"})
    assert resp.json()["data"]["rating"] == "unhelpful"
    stats = client.get("/api/feedback/stats").json()["data"]
    assert stats["total"] == 2
    assert stats["helpful"] == 1


def test_feedback_invalid_rating(client):
    cid = _make_complaint(client)
    resp = client.post("/api/feedback", json={"complaint_id": cid, "rating": "bad"})
    assert resp.status_code == 400


# ---------- 证据上传 ----------

def _tiny_png() -> bytes:
    # 1x1 PNG
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_evidence_upload(client):
    files = [
        ("files", ("order.png", _tiny_png(), "image/png")),
        ("files", ("chat.png", _tiny_png(), "image/png")),
    ]
    resp = client.post("/api/evidence/upload", files=files, data={"user_id": "test"})
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert len(items) == 2
    assert all("/files/evidence/" in it["file_url"] for it in items)


def test_evidence_upload_bad_type(client):
    files = [("files", ("bad.txt", b"hello", "text/plain"))]
    resp = client.post("/api/evidence/upload", files=files)
    assert resp.status_code == 400


# ---------- 证据随生成保存 ----------

def test_complaint_saves_evidence(client):
    evidence = [
        {"file_name": "order.png", "file_url": "/files/evidence/a.png", "order_info": {"platform": "拼多多"}}
    ]
    resp = client.post("/api/complaint/text", json={"text": SAMPLE_TEXT, "evidence": evidence})
    data = resp.json()["data"]
    assert data["evidence"] == evidence

    cid = data["id"]
    detail = client.get(f"/api/complaint/{cid}").json()["data"]
    assert detail["evidence"][0]["file_url"] == "/files/evidence/a.png"


# ---------- 云调用 JSON 接口 ----------

def test_voice_json_demo_mode(client):
    """演示模式下 voice-json 应返回友好提示（演示模式不支持语音）"""
    import base64
    payload = base64.b64encode(b"fake-audio-bytes").decode()
    resp = client.post("/api/complaint/voice-json", json={
        "audio_base64": payload,
        "audio_name": "voice.wav",
        "user_id": "t",
    })
    assert resp.status_code == 400
    assert "演示模式" in resp.json()["detail"] or "语音" in resp.json()["detail"]


def test_evidence_upload_json(client):
    import base64
    img = _tiny_png()
    resp = client.post("/api/evidence/upload-json", json={
        "files": [{"name": "order.png", "base64": base64.b64encode(img).decode()}],
        "user_id": "t",
    })
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert len(items) == 1
    assert items[0]["file_base64"], "应返回 base64 供前端展示"


def test_evidence_upload_json_invalid_base64(client):
    resp = client.post("/api/evidence/upload-json", json={
        "files": [{"name": "a.png", "base64": "!!!not-base64!!!"}],
    })
    assert resp.status_code == 400
