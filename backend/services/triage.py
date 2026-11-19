"""案件智能分诊：规则兜底 + 可选 LLM 结构化增强。"""

import re
from typing import Optional

from ..config import settings
from .llm import chat_json_data

PRIORITIES = ("urgent", "high", "normal", "low")

CATEGORY_RULES = (
    {
        "category": "食品安全",
        "team": "食品与餐饮组",
        "keywords": ("食品", "外卖", "吃出", "异物", "蟑螂", "头发", "过期", "变质", "腹泻", "食物中毒"),
    },
    {
        "category": "网购纠纷",
        "team": "电商与平台组",
        "keywords": ("网购", "淘宝", "天猫", "拼多多", "京东", "直播间", "假货", "仿品", "货不对板", "退一赔三"),
    },
    {
        "category": "预付合同",
        "team": "预付与合同组",
        "keywords": ("预付", "年卡", "会员卡", "办卡", "跑路", "关门", "合同", "定金", "违约"),
    },
    {
        "category": "物流快递",
        "team": "物流与出行组",
        "keywords": ("快递", "物流", "丢件", "签收", "派件", "邮政", "破损"),
    },
    {
        "category": "出行服务",
        "team": "物流与出行组",
        "keywords": ("机票", "酒店", "旅游", "打车", "网约车", "旅行社", "强制购物"),
    },
    {
        "category": "产品质量",
        "team": "产品与售后组",
        "keywords": ("质量", "坏了", "故障", "开裂", "漏水", "三包", "维修", "换新"),
    },
    {
        "category": "价格与宣传",
        "team": "平台治理组",
        "keywords": ("虚假宣传", "广告", "价格欺诈", "乱收费", "扣费", "自动续费", "夸大"),
    },
)

URGENT_SIGNALS = (
    "中毒", "住院", "过敏", "人身伤害", "受伤", "婴儿", "孕妇", "老人",
    "漏电", "爆炸", "起火", "威胁", "限制人身自由",
)

HIGH_SIGNALS = (
    "假货", "欺诈", "跑路", "失联", "拒不退款", "拒绝退款", "食品安全",
    "退一赔三", "退一赔十", "行政处罚", "多人", "群体",
)

ALLOWED_CATEGORIES = tuple(rule["category"] for rule in CATEGORY_RULES) + ("其他",)
ALLOWED_TEAMS = tuple(dict.fromkeys(rule["team"] for rule in CATEGORY_RULES)) + ("综合处理组",)


def _amount_from_text(raw_text: str, order_info: Optional[dict]) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*元", raw_text or "")
    raw_amount = match.group(1) if match else (order_info or {}).get("amount", "")
    try:
        return float(raw_amount)
    except (TypeError, ValueError):
        return 0.0


def _match_category(raw_text: str, existing_category: str) -> tuple[dict, list]:
    best_rule = None
    best_hits = []
    for rule in CATEGORY_RULES:
        hits = [keyword for keyword in rule["keywords"] if keyword in raw_text]
        if existing_category == rule["category"]:
            hits.append(f"已有类别:{existing_category}")
        if len(hits) > len(best_hits):
            best_rule = rule
            best_hits = hits
    if best_rule is None:
        return {"category": existing_category or "其他", "team": "综合处理组"}, []
    return best_rule, best_hits


def _rule_triage(
    raw_text: str,
    existing_category: str = "",
    order_info: Optional[dict] = None,
    evidence: Optional[list] = None,
) -> dict:
    text = raw_text or ""
    rule, category_hits = _match_category(text, existing_category)
    urgent_hits = [signal for signal in URGENT_SIGNALS if signal in text]
    high_hits = [signal for signal in HIGH_SIGNALS if signal in text]
    amount = _amount_from_text(text, order_info)

    if urgent_hits:
        priority = "urgent"
    elif high_hits or rule["category"] in ("食品安全", "网购纠纷") or amount >= 3000:
        priority = "high"
    elif category_hits or evidence:
        priority = "normal"
    else:
        priority = "low"

    signals = list(dict.fromkeys(category_hits + urgent_hits + high_hits))
    if amount >= 3000:
        signals.append(f"涉及金额 {amount:g} 元")
    evidence_count = len(evidence or [])
    if evidence_count:
        signals.append(f"已登记 {evidence_count} 项证据")

    confidence = 0.46
    confidence += min(len(category_hits), 4) * 0.1
    confidence += 0.12 if urgent_hits else 0
    confidence += 0.06 if evidence_count else 0
    confidence = round(min(confidence, 0.94), 2)

    reason_parts = [f"匹配到{rule['category']}特征"]
    if urgent_hits:
        reason_parts.append(f"包含高风险信号：{'、'.join(urgent_hits)}")
    elif high_hits:
        reason_parts.append(f"包含高优先级信号：{'、'.join(high_hits)}")
    elif rule["category"] in ("食品安全", "网购纠纷"):
        reason_parts.append("该类别默认进入较优先队列")
    if amount:
        reason_parts.append(f"识别金额 {amount:g} 元")

    return {
        "category": rule["category"],
        "priority": priority,
        "team": rule["team"],
        "confidence": confidence,
        "reason": "；".join(reason_parts),
        "signals": signals[:10],
        "source": "rule",
    }


def _normalize_llm_result(data: dict, fallback: dict) -> dict:
    category = data.get("category")
    priority = data.get("priority")
    team = data.get("team")
    if category not in ALLOWED_CATEGORIES or priority not in PRIORITIES or team not in ALLOWED_TEAMS:
        raise ValueError("分诊结果包含非法枚举值")
    try:
        confidence = round(max(0.0, min(float(data.get("confidence")), 1.0)), 2)
    except (TypeError, ValueError):
        confidence = fallback["confidence"]
    signals = data.get("signals")
    if not isinstance(signals, list):
        signals = fallback["signals"]
    reason = str(data.get("reason") or fallback["reason"]).strip()
    return {
        "category": category,
        "priority": priority,
        "team": team,
        "confidence": confidence,
        "reason": reason[:500],
        "signals": [str(item)[:80] for item in signals[:10]],
        "source": "llm",
    }


def triage_case(
    raw_text: str,
    existing_category: str = "",
    order_info: Optional[dict] = None,
    evidence: Optional[list] = None,
) -> dict:
    """返回可持久化的分诊结果；无 Key、超时或解析失败时回退规则。"""
    fallback = _rule_triage(raw_text, existing_category, order_info, evidence)
    if settings.demo_mode:
        return fallback

    system_prompt = (
        "你是消费维权售后分诊器。只输出 JSON 对象，不要解释。"
        "字段必须为 category、priority、team、confidence、reason、signals。"
        f"category 只能取 {list(ALLOWED_CATEGORIES)}；"
        f"priority 只能取 {list(PRIORITIES)}；"
        f"team 只能取 {list(ALLOWED_TEAMS)}；"
        "confidence 为 0 到 1；signals 为最多 10 个短字符串。"
    )
    human_text = (
        f"已有类别：{existing_category or '无'}\n"
        f"订单信息：{order_info or {}}\n"
        f"证据数量：{len(evidence or [])}\n"
        f"案件描述：{raw_text}"
    )
    try:
        data = chat_json_data(
            system_prompt,
            human_text,
            temperature=0,
            max_tokens=600,
            fallback=fallback,
            model=settings.llm_fast_model,
        )
        if data.get("source") == "rule":
            return fallback
        return _normalize_llm_result(data, fallback)
    except Exception:
        return fallback
