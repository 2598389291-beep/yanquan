"""场景级测试：6 大常见纠纷 + 信息缺失边界 + LLM 降级容错"""

import pytest

from backend.services.complaint_generator import _validate_matched_laws, generate_complaint

SCENARIOS = [
    (
        "网购假货",
        "我在拼多多买了一个蓝牙耳机花了99元，收到发现是假货，和正品完全不一样，商家拒绝退款，我要退一赔三",
        "网购纠纷",
        ["消费者权益保护法"],
        True,
    ),
    (
        "食品安全",
        "我在美团点了一份外卖花了50元，吃到一半发现里面有蟑螂，商家只愿意退餐费，我要退一赔十",
        "食品安全",
        ["食品安全法"],
        True,
    ),
    (
        "快递丢件",
        "我在淘宝买了一件衣服500元，快递显示签收但我没收到，快递公司说查不到，要求赔偿",
        "服务纠纷",
        ["快递暂行条例"],
        True,
    ),
    (
        "预付卡跑路",
        "我在健身房办了年卡花了3000元，才去了两次健身房就关门跑路了，要求退还未使用的费用",
        "合同纠纷",
        ["单用途商业预付卡管理办法"],
        True,
    ),
    (
        "虚假宣传",
        "我在抖音直播间买了护肤品399元，主播说能美白祛斑，用了一个月完全没效果，要求退款赔偿",
        "虚假宣传",
        ["广告法"],
        True,
    ),
    (
        "售后推诿",
        "我在京东买的手机屏幕碎了，客服一直推诿不给处理，已经拖了两周，要求尽快处理",
        "服务纠纷",
        ["消费者权益保护法"],
        False,  # 信息不完整场景
    ),
]


@pytest.mark.parametrize("name,text,expect_cat,expect_laws,complete", SCENARIOS)
def test_scenario_pipeline(name, text, expect_cat, expect_laws, complete):
    """6 大常见场景分别跑一遍生成管线（演示模式）"""
    result = generate_complaint(text)
    assert result["complaint_letter"], f"{name}: 投诉信为空"
    assert result["category"] == expect_cat, f"{name}: 类别 {result['category']}"
    law_text = "".join(result["legal_basis"])
    for law in expect_laws:
        assert law in law_text or law in result["complaint_letter"], f"{name}: 缺少法条 {law}"
    assert result["channel_advice"]["channels"], f"{name}: 无渠道建议"
    assert result["negotiation_script"]["steps"], f"{name}: 无话术"
    assert result["merchant_qualification_advice"]["items"], f"{name}: 无资质建议"
    assert result["legal_details"], f"{name}: 无法律溯源"
    # 信息不完整场景应提示补充
    if not complete:
        assert result["suggestions"], f"{name}: 应给出补充建议"


def test_missing_info_placeholder():
    """关键信息缺失时必须用 [请补充] 占位，不编造"""
    result = generate_complaint("我买了东西坏了商家不处理")
    letter = result["complaint_letter"]
    assert ("【请补充" in letter or "[请补充" in letter), "缺失信息未占位"
    # 金额缺失时不应出现具体数字金额
    assert "建议补充" in " ".join(result.get("suggestions") or [])


def test_sanitize_letter_no_fabricated_identity():
    """用户未提供姓名/电话/被投诉方时，生成结果中的编造内容必须被占位替换"""
    from backend.services.complaint_generator import _sanitize_letter
    letter = (
        "投诉人：张三\n联系电话：13812345678\n"
        "被投诉方：深圳市某某科技有限公司\n"
        "正文内容保持正常。"
    )
    facts = {"seller": "", "amount": "99", "issue_date": "2026年1月1日"}
    out = _sanitize_letter(letter, facts)
    assert "【请补充姓名】" in out
    assert "【请补充手机号】" in out
    assert "【请补充被投诉方全称】" in out
    assert "张三" not in out
    assert "13812345678" not in out
    assert "某某科技" not in out


def test_validate_matched_laws_filters_hallucination():
    """LLM 返回的幻觉法条应被过滤"""
    matched = [
        {"law_name": "消费者权益保护法", "article": "第55条", "content": "旧内容"},
        {"law_name": "不存在的法律", "article": "第1条", "content": "幻觉"},
    ]
    filtered = _validate_matched_laws(matched)
    assert len(filtered) == 1
    assert filtered[0]["law_name"] == "消费者权益保护法"
    assert "欺诈" in filtered[0]["content"], "应使用知识库原文覆盖"


def test_llm_total_failure_falls_back(monkeypatch):
    """LLM 全线失败时，管线自动降级为规则生成，不崩溃"""
    from backend.config import settings
    from backend.services import llm

    # 强制走 LLM 模式
    monkeypatch.setattr(settings, "dashscope_api_key", "sk-real-key-for-test")

    def boom(*args, **kwargs):
        raise RuntimeError("模拟外部 API 故障")

    monkeypatch.setattr(llm, "chat_json_data", boom)
    monkeypatch.setattr(llm, "chat_json_list", boom)

    result = generate_complaint("我在淘宝买了衣服299元，收到是假货，商家不退款")
    assert result["complaint_letter"], "降级后投诉信为空"
    assert result["category"] == "网购纠纷"
    assert result["legal_basis"]
    assert result["negotiation_script"]["steps"]
    assert result["channel_advice"]["channels"]
