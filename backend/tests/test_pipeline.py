"""核心管线逻辑测试（演示模式）"""

from backend.services.advice import get_channel_advice, get_merchant_qualification_advice
from backend.services.complaint_generator import generate_complaint
from backend.services.demo import extract_facts, generate_letter, match_laws


# ---------- 演示管线 ----------

def test_demo_pipeline_full_structure():
    result = generate_complaint(
        "我在拼多多买了一个蓝牙耳机花了99元，收到后发现是假货，和正品完全不一样，商家还不退款，我要退一赔三。"
    )
    assert result["category"] == "网购纠纷"
    assert result["complaint_letter"]
    assert "消费者权益保护法" in result["legal_basis"][0] or "退一赔三" in result["complaint_letter"]
    assert result["action_path"][0]["step"] == 1
    assert result["channel_advice"]["channels"]
    assert result["negotiation_script"]["steps"]
    assert result["merchant_qualification_advice"]["items"][0]["qualification"] == "营业执照"


def test_demo_extract_facts():
    facts = extract_facts("我在美团点了一份外卖花了50元，吃出蟑螂，要求赔偿1000元")
    assert facts["platform"] == "美团"
    assert facts["amount"] == "50"
    assert facts["category"] == "食品安全"
    assert "蟑螂" in facts["issue_description"]


def test_demo_extract_facts_fallback():
    facts = extract_facts("买了东西坏了")
    assert facts["amount"] == ""
    assert any("金额" in item for item in facts["missing_fields"])


def test_demo_letter_contains_facts():
    facts = extract_facts("我在京东买了手机花了3000元，屏幕碎了，商家不保修")
    laws = match_laws(facts)
    result = generate_letter(facts, laws)
    assert "3000" in result["complaint_letter"]
    assert "京东" in result["complaint_letter"]
    assert result["action_path"]


# ---------- 法律匹配 ----------

def test_match_laws_fake_goods():
    facts = {"issue_type": "假货", "category": "网购纠纷", "issue_description": "收到假货要求退一赔三", "desired_outcome": "退一赔三"}
    laws = match_laws(facts)
    names = [f"{l['law_name']} {l['article']}" for l in laws]
    assert any("消费者权益保护法" in n and "55" in n for n in names), names


def test_match_laws_food():
    facts = {"issue_type": "食品安全", "category": "食品安全", "issue_description": "吃出异物要求退一赔十", "desired_outcome": "退一赔十"}
    laws = match_laws(facts)
    names = [f"{l['law_name']} {l['article']}" for l in laws]
    assert any("食品安全法" in n and "148" in n for n in names), names


# ---------- 渠道建议 ----------

def test_channel_advice_online_fake_goods():
    facts = {"category": "网购纠纷", "issue_type": "假货", "amount": "299", "desired_outcome": "退一赔三", "platform": "拼多多"}
    result = get_channel_advice(facts, [{"law_name": "消费者权益保护法"}, {"law_name": "电子商务法"}])
    channels = [c["channel"] for c in result["channels"]]
    assert channels[0] == "平台客服协商"
    assert "12315 投诉" in channels
    assert "法院起诉" not in channels


def test_channel_advice_food_report():
    facts = {"category": "食品安全", "issue_type": "食品安全", "amount": "50", "desired_outcome": "退一赔十", "platform": "美团"}
    result = get_channel_advice(facts, [{"law_name": "食品安全法"}])
    channels = [c["channel"] for c in result["channels"]]
    assert "12315 举报" in channels
    assert "12315 投诉" in channels


def test_channel_advice_large_amount_lawsuit():
    facts = {"category": "合同纠纷", "issue_type": "合同违约", "amount": "20000", "desired_outcome": "退款", "platform": ""}
    result = get_channel_advice(facts, [{"law_name": "民法典"}])
    channels = [c["channel"] for c in result["channels"]]
    assert "法院起诉" in channels
    assert "平台客服协商" not in channels


def test_channel_advice_priority_sorted():
    facts = {"category": "网购纠纷", "issue_type": "假货", "amount": "8000", "desired_outcome": "退款", "platform": "淘宝"}
    result = get_channel_advice(facts, [{"law_name": "消费者权益保护法"}])
    priorities = [c["priority"] for c in result["channels"]]
    assert priorities == sorted(priorities)


# ---------- 资质建议 ----------

def test_qualification_food():
    facts = {"category": "食品安全", "issue_type": "食品变质", "seller": "XX小吃店", "platform": "美团"}
    result = get_merchant_qualification_advice(facts)
    quals = [q["qualification"] for q in result["items"]]
    assert "营业执照" in quals
    assert "食品经营许可证" in quals
    assert result["merchant_name"] == "XX小吃店"


def test_qualification_electronics_3c():
    facts = {"category": "产品质量", "issue_type": "充电器质量不合格", "seller": "XX数码店", "platform": "拼多多"}
    result = get_merchant_qualification_advice(facts)
    quals = [q["qualification"] for q in result["items"]]
    assert any("3C" in q for q in quals)


def test_qualification_offline_default():
    facts = {"category": "其他", "issue_type": "其他", "seller": "", "platform": ""}
    result = get_merchant_qualification_advice(facts)
    quals = [q["qualification"] for q in result["items"]]
    assert "营业执照" in quals
    assert result["merchant_name"] == "该商家"
