"""客服回复建议与法条候选约束测试。"""

from backend.services.reply_suggestion import build_reply_suggestion


def test_reply_suggestion_uses_retrieved_laws():
    result = build_reply_suggestion(
        "外卖里吃到蟑螂，商家只肯退餐费，我要赔偿医药费",
        category="食品安全",
        evidence=[{"file_name": "就医记录.png"}],
    )
    assert result["reply"]
    assert result["source"] == "template"
    assert result["citations"]
    assert all(citation["law_name"] and citation["article"] for citation in result["citations"])
    assert all(citation["source_url"].startswith("https://flk.npc.gov.cn/") for citation in result["citations"])
    assert result["next_actions"]


def test_reply_suggestion_flags_low_evidence():
    result = build_reply_suggestion("商家拒绝退款", category="服务纠纷")
    assert "证据材料不足" in result["risk_flags"]
