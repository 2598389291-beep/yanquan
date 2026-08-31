"""数据库层测试"""

import pytest

from backend import database as db


def _make_complaint(user_id="test_user") -> dict:
    return db.save_complaint(
        user_id=user_id,
        raw_text="测试维权经历",
        complaint_letter="测试投诉信",
        legal_basis=[{"law_name": "消费者权益保护法", "article": "第55条"}],
        action_path=[{"step": 1, "action": "联系平台"}],
        category="网购纠纷",
        order_info={"platform": "拼多多"},
    )


def test_initial_status():
    record = _make_complaint()
    assert record["status"] == "generated"


def test_status_flow():
    record = _make_complaint()
    for new_status in ("copied", "submitted", "following_up", "resolved"):
        updated = db.update_complaint_status(record["id"], "test_user", new_status)
        assert updated["status"] == new_status


def test_invalid_status_rejected():
    record = _make_complaint()
    with pytest.raises(ValueError):
        db.update_complaint_status(record["id"], "test_user", "invalid")


def test_wrong_user_rejected():
    record = _make_complaint(user_id="user_a")
    assert db.update_complaint_status(record["id"], "user_b", "resolved") is None


def test_delete_ownership():
    record = _make_complaint(user_id="user_a")
    assert db.delete_complaint(record["id"], "user_b") is False
    assert db.delete_complaint(record["id"], "user_a") is True


def test_stats():
    _make_complaint("u1")
    _make_complaint("u1")
    stats = db.get_complaint_stats("u1")
    assert stats["total"] == 2
    assert stats["categories"] == 1


def test_status_filter():
    _make_complaint("u1")
    r2 = _make_complaint("u1")
    db.update_complaint_status(r2["id"], "u1", "resolved")
    items, total = db.get_complaints("u1", status="resolved")
    assert total == 1
    assert items[0]["status"] == "resolved"
