"""智能分诊规则与持久化测试。"""

from backend.services.triage import triage_case


def test_rule_triage_marks_food_safety_injury_urgent():
    result = triage_case(
        "外卖吃出异物，孕妇吃完住院了，商家只肯退餐费",
        existing_category="食品安全",
        order_info={"amount": "88"},
    )
    assert result["category"] == "食品安全"
    assert result["team"] == "食品与餐饮组"
    assert result["priority"] == "urgent"
    assert result["source"] == "rule"
    assert any("住院" in signal for signal in result["signals"])


def test_rule_triage_marks_fake_goods_high_priority():
    result = triage_case(
        "直播间买的护肤品是假货，商家拒绝退款，我要退一赔三",
        existing_category="网购纠纷",
    )
    assert result["category"] == "网购纠纷"
    assert result["team"] == "电商与平台组"
    assert result["priority"] == "high"
    assert 0 <= result["confidence"] <= 1


def test_rule_triage_falls_back_to_general_team():
    result = triage_case("我遇到了一个不知道该找谁处理的问题")
    assert result["category"] == "其他"
    assert result["team"] == "综合处理组"
    assert result["priority"] == "low"
