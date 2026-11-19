"""客服回复建议：复用法条检索，模型输出受候选引用白名单约束。"""

from typing import Optional

from ..config import settings
from .legal import build_legal_details
from .llm import chat_json_data
from .retrieval import retrieve_laws


def _citation_key(law: dict) -> str:
    return f"{law.get('law_name', '')}|{law.get('article', '')}"


def _fallback_suggestion(
    raw_text: str,
    category: str,
    candidates: list,
    evidence: Optional[list],
) -> dict:
    citations = build_legal_details(candidates[:3])
    evidence_count = len(evidence or [])
    if citations:
        first = citations[0]
        basis = (
            f"根据《{first['law_name']}》{first['article']}，"
            f"{first['content'][:120]}"
        )
    else:
        basis = "当前未检索到可直接引用的法条，请先核实事实和证据。"

    next_actions = [
        "核对用户描述与订单/证据材料是否一致",
        "向用户说明当前可引用的法条依据和下一步处理路径",
    ]
    if evidence_count == 0:
        next_actions.append("请用户补充订单截图、支付记录或沟通凭证")
    else:
        next_actions.append("确认现有证据能否支撑退款、赔偿或平台介入")

    risk_flags = []
    if any(signal in raw_text for signal in ("住院", "受伤", "中毒", "孕妇", "婴儿", "人身")):
        risk_flags.append("涉及人身健康风险，优先人工复核")
    if evidence_count == 0:
        risk_flags.append("证据材料不足")

    reply = (
        "您好，已收到您的反馈。"
        f"{basis}"
        "我们会结合您提供的订单、沟通记录和证据材料继续核实，"
        "并在确认责任后给出进一步处理方案。"
    )
    return {
        "reply": reply,
        "citations": citations,
        "next_actions": next_actions,
        "risk_flags": risk_flags,
        "source": "template",
    }


def _normalize_llm_output(data: dict, fallback: dict, candidates: list) -> dict:
    allowed = {_citation_key(item) for item in candidates}
    citation_by_key = {_citation_key(item): item for item in candidates}
    raw_citations = data.get("citations")
    if not isinstance(raw_citations, list):
        raise ValueError("citations 必须是数组")
    valid_citations = []
    for citation in raw_citations:
        if not isinstance(citation, dict):
            continue
        key = _citation_key(citation)
        if key not in allowed:
            continue
        source = citation_by_key[key]
        valid_citations.append(
            {
                "law_name": source.get("law_name", ""),
                "article": source.get("article", ""),
                "content": source.get("content", ""),
                "source_url": build_legal_details([source])[0]["source_url"],
            }
        )
    if not valid_citations:
        raise ValueError("模型未返回合法候选引用")

    reply = str(data.get("reply") or "").strip()
    if len(reply) < 20:
        raise ValueError("回复建议过短")
    next_actions = data.get("next_actions")
    if not isinstance(next_actions, list):
        next_actions = fallback["next_actions"]
    risk_flags = data.get("risk_flags")
    if not isinstance(risk_flags, list):
        risk_flags = fallback["risk_flags"]
    return {
        "reply": reply[:1500],
        "citations": valid_citations,
        "next_actions": [str(item)[:200] for item in next_actions[:6]],
        "risk_flags": [str(item)[:120] for item in risk_flags[:6]],
        "source": "llm",
    }


def build_reply_suggestion(
    raw_text: str,
    category: str = "",
    evidence: Optional[list] = None,
    k: int = 5,
) -> dict:
    candidates = retrieve_laws(raw_text, k=k)
    fallback = _fallback_suggestion(raw_text, category, candidates, evidence)
    if settings.demo_mode or not candidates:
        return fallback

    system_prompt = (
        "你是消费维权客服回复助手。只输出 JSON，不要输出 Markdown。"
        "字段必须为 reply、citations、next_actions、risk_flags。"
        "citations 中每一项只能使用给定候选法条里的 law_name 和 article，"
        "禁止编造候选之外的法律、条号、事实或承诺。"
        "reply 要专业、克制、可让客服直接修改后发送。"
    )
    candidate_text = "\n".join(
        f"- {item['law_name']} {item['article']}: {item['content'][:220]}"
        for item in candidates
    )
    human_text = (
        f"案件类别：{category or '未分类'}\n"
        f"案件描述：{raw_text}\n"
        f"候选法条：\n{candidate_text}"
    )
    try:
        data = chat_json_data(
            system_prompt,
            human_text,
            temperature=0.1,
            max_tokens=1000,
            fallback=fallback,
            model=settings.llm_fast_model,
        )
        if data.get("source") == "template":
            return fallback
        return _normalize_llm_output(data, fallback, candidates)
    except Exception:
        return fallback
