"""运营控制台静态页面可用性测试。"""


def test_ops_console_is_served(client):
    resp = client.get("/ops/")
    assert resp.status_code == 200
    assert "售后协同台" in resp.text
    assert "app.js" in resp.text


def test_ops_console_assets_are_served(client):
    assert client.get("/ops/styles.css").status_code == 200
    resp = client.get("/ops/app.js")
    assert resp.status_code == 200
    assert "/api/operations/cases" in resp.text
