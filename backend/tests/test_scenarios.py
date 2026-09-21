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


def test_validate_matched_laws_accepts_model_format():
    """模型常把名称写成《XX法》第55条、条号写成中文数字：需归一化后仍能命中知识库"""
    matched = [
        {"law_name": "《消费者权益保护法》第55条", "article": "第55条", "content": "模型自己写的内容"},
        {"law_name": "中华人民共和国消费者权益保护法", "article": "第二十四条", "content": "模型自己写的内容"},
    ]
    filtered = _validate_matched_laws(matched)
    assert len(filtered) == 2, "归一化后应全部命中知识库"
    names = {(law["law_name"], law["article"]) for law in filtered}
    assert ("消费者权益保护法", "第55条") in names
    assert ("消费者权益保护法", "第24条") in names, "中文条号应转成阿拉伯数字"
    for law in filtered:
        assert "模型自己写的内容" not in law["content"], "内容必须用知识库原文覆盖"


def test_validate_matched_laws_dedupes_same_article():
    """同一法条用不同写法重复返回时，应去重"""
    matched = [
        {"law_name": "消费者权益保护法", "article": "第55条", "content": "A"},
        {"law_name": "《消费者权益保护法》第55条", "article": "第55条", "content": "B"},
    ]
    assert len(_validate_matched_laws(matched)) == 1


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


def test_letter_needs_review_detects_problems():
    """规则初筛：缺板块/未引法条时应触发模型质检"""
    from backend.services.complaint_generator import _letter_needs_review

    text = "事实与理由：" + "内容" * 120
    need, issues = _letter_needs_review(text, {"amount": "399", "issue_date": "2026-01-01"}, [])
    assert need is True
    assert any("法律依据" in i or "诉求" in i for i in issues)


def test_letter_needs_review_passes_complete_letter():
    """板块完整、已引法条、信息齐全的文书不必再花一次模型调用"""
    from backend.services.complaint_generator import _letter_needs_review

    letter = (
        "投诉人：【请补充姓名】\n被投诉方：【请补充被投诉方全称】\n"
        "投诉事项：购买商品存在欺诈行为\n"
        "事实与理由：" + "内容" * 120 + "\n"
        "法律依据：《消费者权益保护法》第55条\n"
        "诉求：退款 399 元\n"
        "时间：2026 年 1 月 1 日，金额：399 元\n"
    )
    need, issues = _letter_needs_review(
        letter,
        {"amount": "399", "issue_date": "2026-01-01"},
        [{"law_name": "消费者权益保护法"}],
    )
    assert need is False, f"不应触发质检，却命中：{issues}"


def test_verify_facts_drops_hallucinated_fields():
    """事实核验：用户原话里没有的金额/日期/商家名，不能被当成事实带到文书里"""
    from backend.services.complaint_generator import _verify_facts_against_text

    facts = {
        "amount": "899",
        "issue_date": "2024年5月10日",
        "seller": "某某科技有限公司",
        "platform": "抖音",
        "missing_fields": [],
    }
    raw = "在抖音直播间买了一套护肤品 899 元，收到发现是假货，商家拒绝退款"
    out = _verify_facts_against_text(facts, raw)

    assert out["amount"] == "899", "原文确实提到的金额应保留"
    assert out["platform"] == "抖音", "原文提到的平台应保留"
    assert out["issue_date"] == "", "原文未提及的日期应清空"
    assert out["seller"] == "", "原文未提及的商家名应清空"
    assert any("购买时间" in m for m in out["missing_fields"])
def test_sanitize_letter_is_idempotent():
    """净化函数重复调用不能产生重复占位符（模型可能自己就写了占位符）"""
    from backend.services.complaint_generator import _sanitize_letter

    letter = "投诉人：【请补充姓名】\n联系电话：【请补充手机号】\n被投诉方：【请补充被投诉方全称】\n事实与理由：不详" * 5
    once = _sanitize_letter(letter, {"amount": "", "issue_date": "", "seller": ""})
    twice = _sanitize_letter(once, {"amount": "", "issue_date": "", "seller": ""})
    assert once == twice, "重复净化不应产生任何变化"
    assert "【请补充姓名】【请补充姓名】" not in twice


def test_sanitize_letter_removes_dashed_phone():
    """带分隔符的编造手机号（138-1234-5678）也必须被替换"""
    from backend.services.complaint_generator import _sanitize_letter

    for raw_phone in ("138-1234-5678", "138 1234 5678", "13812345678"):
        out = _sanitize_letter(f"联系电话：{raw_phone}\n事实与理由：不详", {"amount": "", "issue_date": "", "seller": ""})
        assert raw_phone not in out, f"{raw_phone} 未被替换"
        assert "请补充手机号" in out
    # 公共热线不能被误伤
    keep = _sanitize_letter("可拨打 12315 或快递公司热线 95311 反映", {})
    assert "12315" in keep and "95311" in keep
