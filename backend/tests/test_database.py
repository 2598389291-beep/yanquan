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


def test_seed_syncs_changed_article():
    """知识库条文被修正后，已存在的库应被更新，而不是停留在旧内容。

    背景：老实现是"表非空就跳过"，导致法条内容和标签改过之后，
    已有数据库永远拿不到新版本（线上重建库才碰巧是新的）。
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE legal_knowledge SET content = '旧内容', tags = '[\"旧标签\"]' "
        "WHERE law_name = '食品安全法' AND article = '第148条'"
    )
    conn.commit()

    db._seed_legal_knowledge(cursor)
    conn.commit()

    row = cursor.execute(
        "SELECT content, tags FROM legal_knowledge WHERE law_name = '食品安全法' AND article = '第148条'"
    ).fetchone()
    conn.close()

    assert "十倍" in row["content"], "内容应被知识库最新版本覆盖"
    assert row["tags"] != '["旧标签"]', "标签也应同步更新"


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
