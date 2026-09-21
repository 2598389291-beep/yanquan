"""投诉生成管线 — 多步 AI 管线（LLM 模式） + 演示模式分发

流程：
1. 事实提取（LLM，结构化关键信息）
2. 法律检索（LLM 语义匹配本地法律知识库；预留外部法律 API）
3. 投诉信生成（LLM，事实 + 法律 + 渠道建议）
4. 商家资质建议（规则驱动，无需 LLM）
5. 自我审查（LLM 质检 + 自动修复）
6. 渠道建议 + 沟通话术模板

未配置 API Key 时（settings.demo_mode=True），自动切换为 services/demo.py
的纯规则管线，保证项目开箱可演示、可测试。
"""

import json
import logging
import re
from typing import Callable, Optional

from ..config import settings
from ..database import get_legal_knowledge
from . import llm
from .advice import get_channel_advice, get_merchant_qualification_advice

logger = logging.getLogger(__name__)

FACT_DEFAULTS = {
    "platform": "", "product": "", "amount": "", "issue_date": "",
    "seller": "", "issue_type": "", "issue_description": "",
    "desired_outcome": "", "missing_fields": [], "category": "其他",
}


# ============================================================
#  Step 1: 事实提取
# ============================================================

# ============================================================
#  Step 1: 事实提取
# ============================================================

def _number_in_text(value: str, text: str) -> bool:
    """判断一个数字类的值是否真的在用户原话里出现过（避免模型自己填金额/日期）"""
    nums = re.findall(r"\d+", str(value or ""))
    if not nums:
        return False
    text_nums = re.findall(r"\d+", text or "")
    joined = "".join(text_nums)
    # 每个数字片段都要能在原文里找到（或者作为原文数字串的一部分）
    return all(n in text_nums or n in joined for n in nums)


def _verify_facts_against_text(facts: dict, raw_text: str, order_info: Optional[dict] = None) -> dict:
    """把事实提取结果与用户原话交叉核对：用户没提过的关键信息一律清空。

    模型有时会把"合理推测"当成事实（例如自己编一个购买日期、金额、商家名称），
    这些信息一旦写进投诉信就是硬伤。这里在进入后续环节之前先做一次事实核验。
    """
    raw = raw_text or ""
    order_blob = json.dumps(order_info or {}, ensure_ascii=False)
    missing = list(facts.get("missing_fields") or [])

    def _clear(key: str, label: str, ok: bool) -> None:
        value = str(facts.get(key) or "").strip()
        if value and not ok:
            logger.warning("事实核验：%s=%r 未在用户原话中出现，已清除", key, value)
            facts[key] = ""
            note = f"未提及{label}"
            if note not in missing:
                missing.append(note)

    _clear("amount", "具体金额", _number_in_text(str(facts.get("amount") or ""), raw + order_blob))
    _clear("issue_date", "购买时间", _number_in_text(str(facts.get("issue_date") or ""), raw))
    for key, label in (("seller", "商家名称"), ("platform", "电商平台")):
        value = str(facts.get(key) or "").strip()
        if value and value not in raw and value not in order_blob:
            _clear(key, label, False)

    facts["missing_fields"] = missing
    return facts


def _extract_facts(raw_text: str, order_info: Optional[dict] = None) -> dict:


    """从用户口述中提取结构化事实（LLM），失败时回退最小结构"""

    order_context = ""
    if order_info and any(order_info.values()):
        parts = []
        for key, label in [("platform", "电商平台"), ("order_number", "订单编号"),
                           ("order_date", "下单时间"), ("product_name", "商品名称"),
                           ("amount", "订单金额"), ("seller", "商家名称")]:
            val = order_info.get(key)
            if val:
                parts.append(f"- {label}：{val}")
        if parts:
            order_context = "## 订单信息（来自截图识别）\n" + "\n".join(parts) + "\n"

    system_prompt = (
        "你是一个专业的消费者维权信息提取助手。你的任务是从用户口述的维权经历中，提取关键的结构化信息。\n\n"
        "请严格按照以下 JSON 格式输出，不要输出任何其他文字：\n"
        "{\n"
        '    "platform": "电商平台名称，如淘宝、拼多多、京东、美团等，无法确定时填空字符串",\n'
        '    "product": "商品或服务名称",\n'
        '    "amount": "涉及金额，纯数字，如 299",\n'
        '    "issue_date": "问题发生的时间或购买时间",\n'
        '    "seller": "商家名称或店铺名",\n'
        '    "issue_type": "问题类型，如假货、质量不合格、虚假宣传、不退款、货不对板、服务差、食品安全等",\n'
        '    "issue_description": "问题的详细描述，尽量完整保留用户原意",\n'
        '    "desired_outcome": "用户期望的解决方案，如退款、换货、赔偿、退一赔三等",\n'
        '    "missing_fields": ["逐条列出用户没有提到的关键信息，如：未提及购买时间、未提及具体金额、未提及商家名称", "..."],\n'
        '    "category": "投诉类别，从以下选择：网购纠纷、服务纠纷、产品质量、食品安全、虚假宣传、价格欺诈、合同纠纷、其他"\n'
        "}\n\n"
        "注意：\n"
        "1. 如果用户提供了订单信息，请直接使用其中的数据填充 platform、product、amount 等字段\n"
        "2. missing_fields 很重要——列出用户没有提到的关键信息，后续生成投诉信时会据此提示用户补充\n"
        "3. 金额统一提取纯数字，不要带单位"
    )

    human_text = f"{order_context}请提取以下维权经历中的关键信息：\n{raw_text}"

    facts = llm.chat_json_data(
        system_prompt, human_text,
        temperature=0.05, max_tokens=2048, fallback=None,
        model=settings.llm_fast_model,
    )
    if not facts:
        facts = {**FACT_DEFAULTS, "issue_description": raw_text}

    for k, v in FACT_DEFAULTS.items():
        facts.setdefault(k, v)

    # 合并 OCR 订单信息（覆盖 facts 中的空缺字段）
    if order_info:
        if order_info.get("platform") and not facts.get("platform"):
            facts["platform"] = order_info["platform"]
        if order_info.get("product_name") and not facts.get("product"):
            facts["product"] = order_info["product_name"]
        if order_info.get("amount") and not facts.get("amount"):
            facts["amount"] = order_info["amount"]
        if order_info.get("seller") and not facts.get("seller"):
            facts["seller"] = order_info["seller"]
        facts["order_info"] = order_info

    # 事实核验：把模型"推测"、但用户从未提过的信息清掉
    facts = _verify_facts_against_text(facts, raw_text, order_info)
    return facts


# ============================================================
#  Step 2: 法律检索
# ============================================================

def _external_law_match(facts: dict) -> Optional[list]:
    """外部法律 API（如北大法宝）检索，预留接口；未配置时返回 None 触发本地回退"""
    if not settings.external_law_api_enabled or not settings.external_law_api_url:
        return None
    # TODO: 接入具体外部法律 API（见 DEPLOY.md / README 说明）
    return None


# 把模型输出的法条名称/条号归一化到知识库的规范格式：
# 《消费者权益保护法》第55条 → (消费者权益保护法, 第55条)
# 中华人民共和国消费者权益保护法 + 第二十三条 → (消费者权益保护法, 第23条)
_ARTICLE_RE = re.compile(r"第[〇零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十]+)?")
_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def _cn_number_to_int(text: str) -> Optional[int]:
    """中文数字转阿拉伯数字（十/十五/二十三/一百零八）；无法解析返回 None"""
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total, current, seen = 0, 0, False
    for ch in text:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
            seen = True
        elif ch in _CN_UNITS:
            total += (current or 1) * _CN_UNITS[ch]
            current = 0
            seen = True
        else:
            return None
    return total + current if seen else None


def normalize_law_name(name: str) -> str:
    """去掉书名号/括号/空格、去掉「中华人民共和国」前缀、剔除混进来的条号"""
    text = _ARTICLE_RE.sub("", name or "")
    text = re.sub(r"[《》【】\[\]（）()\s]", "", text)
    if text.startswith("中华人民共和国"):
        text = text[len("中华人民共和国"):]
    return text


def normalize_article(article: str) -> str:
    """统一成「第N条」（阿拉伯数字），无法解析时原样返回（会被白名单拦下）"""
    text = article or ""
    match = _ARTICLE_RE.search(text)
    token = match.group(0) if match else text
    number = _cn_number_to_int(re.sub(r"[第条之\s]", "", token))
    return f"第{number}条" if number is not None else re.sub(r"\s", "", text)


def _validate_matched_laws(matched: list) -> list:


    """过滤 LLM 返回的法条，仅保留知识库中真实存在的条文（防幻觉）

    LLM 常见的格式差异（《》、「中华人民共和国」前缀、条号写成中文数字、
    把条号混进法律名称）都先归一化，再与知识库精确比对；命中后一律用知识库
    原文覆盖模型输出，保证引用可溯源、不幻觉。
    """
    kb = get_legal_knowledge()
    index = {
        (normalize_law_name(law["law_name"]), normalize_article(law["article"])): law
        for law in kb
    }
    filtered: list = []
    seen: set = set()
    for law in matched or []:
        if not isinstance(law, dict):
            continue
        name = normalize_law_name(law.get("law_name") or "")
        # 有些模型只填了 law_name（含条号），article 为空，这里兜底再解析一次
        article = normalize_article(law.get("article") or law.get("law_name") or "")
        hit = index.get((name, article))
        if not hit:
            continue
        key = (hit["law_name"], hit["article"])
        if key in seen:
            continue
        seen.add(key)
        # 统一为知识库的规范名称/条号/原文
        filtered.append({
            **law,
            "law_name": hit["law_name"],
            "article": hit["article"],
            "content": hit["content"],
        })
    return filtered


def _match_laws(facts: dict, raw_text: str = "") -> list:
    """LLM 语义匹配本地法律知识库，选 1-3 条最相关条文

    raw_text 不为空时会把用户原话一并拼进检索查询，这样本步可以跟事实提取并行执行
    （检索只依赖文本，不依赖结构化结果），实测可省下一次串行模型调用的等待。
    """
    external_result = _external_law_match(facts)
    if external_result is not None:
        return external_result

    all_laws = get_legal_knowledge()
    if not all_laws:
        return []

    # RAG 召回：先按检索相关性召回候选条文，LLM 只从候选中精排，降低幻觉
    from .retrieval import retrieve_laws
    query = " ".join([
        str(facts.get("issue_type", "")), str(facts.get("category", "")),
        str(facts.get("issue_description", ""))[:200], str(facts.get("desired_outcome", "")),
    ])
    if raw_text:
        query = f"{query} {raw_text[:200]}".strip()
    candidates = retrieve_laws(query, k=10)
    if not candidates:
        candidates = all_laws

    laws_text = ""
    for i, law in enumerate(candidates, 1):
        tags = law["tags"] if isinstance(law["tags"], list) else json.loads(law["tags"])
        laws_text += (
            f"{i}. 《{law['law_name']}》{law['article']}\n"
            f"   内容：{law['content']}\n"
            f"   适用标签：{', '.join(tags)}\n\n"
        )

    issue_context = (
        f"问题类型：{facts.get('issue_type', '未知')}\n"
        f"问题描述：{facts.get('issue_description', '')[:200]}\n"
        f"用户诉求：{facts.get('desired_outcome', '未知')}\n"
        f"投诉类别：{facts.get('category', '未知')}"
    )

    system_prompt = (
        "你是一个法律条文匹配专家。你的任务是根据用户维权经历的关键信息，从以下法律知识库中选出最相关的 1-3 条法律条文。\n\n"
        "选择标准：\n"
        "1. 法律条文的内容与用户的问题类型直接相关\n"
        "2. 优先选择最具体、最针对用户问题的法律\n"
        "3. 如果用户问题涉及多个法律领域，最多选 3 条\n"
        "4. 如果没有任何法律条文与用户问题相关，返回空数组\n\n"
        "严格按照以下 JSON 格式输出，只输出一个数组：\n"
        '[\n'
        '    {"law_name": "法律名称（不要书名号、不要带条号，例如：消费者权益保护法）", "article": "第X条（用阿拉伯数字，例如：第55条）", "content": "法律条文原文", "relevance_reason": "选择该条文的理由"}\n'
        "]"
    )

    human_text = f"## 法律知识库\n{laws_text}\n## 用户维权信息\n{issue_context}\n\n请从以上法律知识库中选出最相关的法律条文："
    matched = llm.chat_json_list(system_prompt, human_text, temperature=0.05, max_tokens=2048, fallback=[], model=settings.llm_fast_model)
    return matched if isinstance(matched, list) else []




# ============================================================
#  Step 3b: 投诉信骨架（快速版，先给用户看内容）
# ============================================================

def _generate_skeleton(facts: dict, matched_laws: list) -> str:
    """快速生成投诉信骨架（fast 模型，目标 10 秒内出稿，供任务式轮询展示）"""
    legal_text = "\n".join([f"- 《{l['law_name']}》{l['article']}" for l in matched_laws]) or "（待补充）"
    fact_summary = (
        f"平台：{facts.get('platform', '未提及')}；商品：{facts.get('product', '未提及')}；"
        f"金额：{facts.get('amount', '未提及')}元；时间：{facts.get('issue_date', '未提及')}；"
        f"商家：{facts.get('seller', '未提及')}；问题：{facts.get('issue_type', '未提及')}；"
        f"描述：{str(facts.get('issue_description', ''))[:120]}；诉求：{facts.get('desired_outcome', '未提及')}"
    )
    system_prompt = (
        "你是消费者维权投诉信撰写专家。请根据以下事实和法律条文，快速生成一封投诉信的骨架（不是完整长信）。\n"
        "必须按下面六个板块输出，每板块 1-3 句：\n"
        "【投诉人信息】\n【被投诉方】\n【投诉事项】\n【事实与理由】\n【法律依据】\n【诉求】\n\n"
        "要求：\n"
        "1. 全文 250-450 字，语气客观坚定、有理有据\n"
        "2. 事实板块只写已确认的事实；未提供的信息写【请补充】，严禁编造\n"
        "3. 法律依据写《法律名称》第X条，并用一句话说明其与本案的关系\n"
        "4. 口语表达转成规范书面语（例如“商家太坑了”改为“被投诉方存在损害消费者权益的行为”）\n" \
        "5. 用户未提供姓名/电话/被投诉方全称时，对应位置一律写【请补充】，绝不能编造\n"
        "直接输出骨架文本，不要任何解释或前后缀。"
    )
    human = f"## 事实\n{fact_summary}\n## 法律\n{legal_text}\n\n请生成投诉信骨架。"
    try:
        letter = llm.chat_json(system_prompt, human, temperature=0.2, max_tokens=1000, model=settings.llm_fast_model)
        return letter.strip() if letter and letter.strip() else ""
    except Exception as e:
        logger.warning("骨架生成失败：%s", e)
        return ""

# ============================================================
#  Step 3: 投诉信生成
# ============================================================

def _sanitize_letter(letter: str, facts: dict) -> str:
    """代码级兜底：用户未提供的信息若被模型编造，一律替换为 [请补充] 占位"""
    amount = facts.get("amount") or ""
    issue_date = facts.get("issue_date") or ""
    order_number = (facts.get("order_info") or {}).get("order_number") or ""
    seller = facts.get("seller") or ""

    if not amount:
        letter = re.sub(r"人民币\s*[\d,，.]+\s*元", "【请补充具体金额】", letter)
        letter = re.sub(r"(?<![\d.])[\d,，]{2,}\s*元", "【请补充具体金额】", letter)
    if not issue_date:
        letter = re.sub(r"20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", "【请补充购买时间】", letter)
    if not order_number:
        letter = re.sub(r"订单号[:：]?\s*[A-Za-z0-9\-]{6,}", "【请补充订单号】", letter)

    # 投诉人信息：姓名/电话从不收集，出现具体值一律视为编造
    # 只匹配行首；紧跟占位符时整体不匹配（避免回溯导致重复替换，保证幂等）
    letter = re.sub(
        r"(?m)^[ \t]*投诉人(?![:：]?\s*【请补充)[:：]?\s*[^\n【]*",
        "投诉人：【请补充姓名】",
        letter,
    )
    # 手机号：兼容「13812345678」「138-1234-5678」「138 1234 5678」「+86 138…」等写法
    phone_value = r"(?:\+?86[\s-]?)?(?:1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}|0\d{2,3}[\s-]?\d{7,8})"
    letter = re.sub(
        rf"(联系电话|手机号|手机|电话|联系方式)[:：]?\s*{phone_value}",
        lambda m: f"{m.group(1)}：【请补充手机号】",
        letter,
    )
    # 兜底：正文中孤立出现的手机号（12315 / 95311 等公共热线不会命中，因为第二位不是 3-9）
    letter = re.sub(rf"(?<![\d-]){phone_value}(?![\d-])", "【请补充手机号】", letter)

    if not seller:
        # 被投诉方：整行值替换为占位（防止编造公司名/对象）
        letter = re.sub(
            r"(?m)^[ \t]*(被投诉方|投诉对象|投诉单位|被诉方)(?![:：]?\s*【请补充)[:：]?\s*[^\n【]*",
            "被投诉方：【请补充被投诉方全称】",
            letter,
        )
        # 兜底：括号内疑似公司名（含有限公司/科技/贸易等字样）替换为占位
        letter = re.sub(r"（[^）【]*?(?:有限公司|公司|集团|贸易|科技|商贸|网络科技)[^）【]*?）", "（【请补充商家全称】）", letter)
    return letter


def _generate_complaint_letter(facts: dict, matched_laws: list) -> dict:
    """根据结构化事实和法律条文生成投诉信 + 维权路径"""

    legal_text = "## 适用法律依据\n"
    if matched_laws:
        for law in matched_laws:
            legal_text += f"- 《{law['law_name']}》{law['article']}：{law['content']}\n"
    else:
        legal_text += "（未找到完全匹配的法律条文，请参考通用法律原则）\n"

    fact_summary = (
        f"- 投诉类别：{facts.get('category', '待确定')}\n"
        f"- 涉及平台：{facts.get('platform', '未提及')}\n"
        f"- 商品/服务：{facts.get('product', '未提及')}\n"
        f"- 涉及金额：{facts.get('amount', '未提及')} 元\n"
        f"- 问题时间：{facts.get('issue_date', '未提及')}\n"
        f"- 商家名称：{facts.get('seller', '未提及')}\n"
        f"- 问题类型：{facts.get('issue_type', '未提及')}\n"
        f"- 问题描述：{facts.get('issue_description', '')}\n"
        f"- 用户诉求：{facts.get('desired_outcome', '未提及')}\n"
    )

    missing_text = ""
    missing = facts.get('missing_fields', [])
    if missing:
        missing_text = "⚠️ 注意：以下信息用户未提供，请在投诉信中标注 [请补充]，并在结果中提示用户：\n"
        for item in missing:
            missing_text += f"  - {item}\n"
        missing_text += "\n"

    order_info = facts.get("order_info", {})
    order_text = ""
    if order_info and any(order_info.values()):
        order_text = "## 订单信息（来自截图识别，请直接使用）\n"
        mappings = [("platform", "电商平台"), ("order_number", "订单编号"),
                    ("order_date", "下单时间"), ("product_name", "商品名称"),
                    ("amount", "订单金额"), ("seller", "商家名称")]
        for key, label in mappings:
            val = order_info.get(key)
            if val:
                order_text += f"- {label}：{val}\n"
        order_text += "\n"

    channel_advice_summary = get_channel_advice(facts, matched_laws).get("summary", "")

    system_prompt = (
        "你是一个专业的消费者维权投诉信撰写专家。你的任务是根据用户维权经历的事实信息和适用的法律条文，"
        "生成一份高质量的投诉信和详细的维权路径指引。\n\n"
        "## 投诉信写作规范\n"
        "1. 信函必须包含以下板块，缺一不可：投诉人信息（姓名/联系方式）、被投诉方（企业全称）、投诉事项（一句话概括）、事实与理由（时间/平台/商品/金额/经过）、法律依据（引用具体条文）、诉求（明确金额或方式）\n"
        "2. 语气有理有据、不卑不亢：陈述事实客观克制，不情绪化指责，也不卑微乞求；可适度强调法律后果（退一赔三、行政处罚、公开曝光等）\n"
        "3. 事实描述清晰，包含时间、地点、商品/服务、金额、订单号等要素\n"
        "4. 必须引用具体的法律条文作为依据（从提供的法律依据中选择，条文编号与内容必须准确，不得自行杜撰）\n"
        "5. 诉求要具体明确（退款XX元/换货/赔偿等）\n"
        "6. 口语表达转书面：如“商家太坑了”应写为“被投诉方存在虚假宣传、拒不履行售后义务等损害消费者权益的行为”\n"
        "7. 如果提供了订单信息，请直接使用订单信息中的具体数据（订单号、日期、金额、平台、商家等），不要用占位符\n"
        "8. 投诉信格式：先写被投诉方信息，再写投诉事由，然后列事实经过，接着引用法律依据，最后明确诉求\n"
        "9. 投诉信末尾增加威慑语句：'本人保留将此投诉及商家拒不处理的事实公开发布至社交平台、消费保、黑猫投诉等渠道的权利。'\n"
        "10. 严禁编造用户未提供的信息（购买时间、订单号、企业全称、金额、姓名等）：缺失信息一律用 [请补充] 标注，绝不能虚构具体日期、数字或名称。\n" \
        "11. 投诉人姓名与联系电话：用户未提供时一律写【请补充姓名】/【请补充联系电话】，绝不能自拟姓名或号码；被投诉方企业全称：用户未提供时一律写【请补充被投诉方全称】，绝不能用平台名（如拼多多/淘宝）或猜测的公司名充当被投诉对象。\n\n"
        "请严格按照以下 JSON 格式输出，不要输出任何其他文字：\n"
        "{\n"
        '    "complaint_letter": "投诉信全文",\n'
        '    "legal_basis": ["法律名称 第X条", ...],\n'
        '    "action_path": [\n'
        '        {"step": 1, "action": "步骤名称", "detail": "具体操作指引及预计耗时"}\n'
        "    ]\n"
        "}"
    )

    human_text = (
        f"{legal_text}\n{order_text}"
        f"## 用户维权事实\n{fact_summary}\n{missing_text}"
        f"## 渠道建议\n以下是对用户情况的初步判断，请参考：\n{channel_advice_summary}\n\n"
        f"请根据以上信息，生成投诉信和维权路径。"
    )

    data = llm.chat_json_data(system_prompt, human_text, temperature=0.2, max_tokens=2800, fallback=None)
    if not data:
        return {
            "complaint_letter": "",
            "legal_basis": [f"{law['law_name']} {law['article']}" for law in matched_laws],
            "action_path": [],
        }
    data.setdefault("complaint_letter", "")
    data.setdefault("legal_basis", [])
    data.setdefault("action_path", [])
    return data


# ============================================================
#  Step 5: 自我审查
# ============================================================

def _letter_needs_review(letter: str, facts: dict, matched_laws: list) -> tuple:
    """规则初筛：只有文书确实存在缺漏时才值得花一次模型调用去质检。

    返回 (是否需要质检, 命中的问题列表)。校验点是模型质检清单里
    可以被规则判定的部分（板块完整、引用了法条、缺失信息有占位）。
    """
    issues: list = []
    if not letter or len(letter.strip()) < 200:
        issues.append("文书过短或为空")
    for section in ("事实", "法律依据", "诉求"):
        if section not in letter:
            issues.append(f"缺少「{section}」板块")
    if matched_laws and not any(law.get("law_name") and law["law_name"] in letter for law in matched_laws):
        issues.append("未引用匹配到的法条")
    if not facts.get("amount") and "请补充具体金额" not in letter and "金额" not in letter:
        issues.append("金额缺失且未标注占位")
    if not facts.get("issue_date") and "请补充购买时间" not in letter and "时间" not in letter:
        issues.append("时间缺失且未标注占位")
    return (len(issues) > 0, issues)


# ============================================================
#  Step 5: 自我审查
# ============================================================

def _self_review(result: dict, facts: dict, matched_laws: list) -> dict:




    """LLM 质检投诉信质量并自动修复（金额/法条/诉求/格式等）"""

    complaint_letter = result.get("complaint_letter", "")
    if not complaint_letter:
        return result

    expected_laws = [f"{law['law_name']} {law['article']}" for law in matched_laws]

    system_prompt = (
        "你是一个投诉信质量审查专家。你的任务是对一份投诉信进行质量检查，并给出改进建议。\n\n"
        "检查标准：\n"
        "1. 是否包含具体金额（数字）\n"
        "2. 是否引用法律条文（至少引用一条具体法律）\n"
        "3. 是否包含明确诉求（退款XX元/换货/赔偿等）\n"
        "4. 是否包含具体时间（购买时间或问题发生时间）\n"
        "5. 是否包含商家/平台名称\n"
        "6. 投诉信格式是否规范（有被投诉方、事实陈述、法律依据、诉求）\n"
        "7. 法律引用是否准确，是否与提供的法律依据一致\n\n"
        "严格按照以下 JSON 格式输出：\n"
        "{\n"
        '    "passed": true/false,\n'
        '    "issues": ["问题1", "问题2", ...],\n'
        '    "improved_letter": "改进后的投诉信全文（如果 passed 为 false，则提供一个改进版本）",\n'
        '    "improved_legal_basis": ["改进后的法律依据列表"],\n'
        '    "suggestions": ["给用户的补充建议，如：建议补充购买时间"]\n'
        "}"
    )

    expected_laws_text = "\n".join([f"- 应引用：{law}" for law in expected_laws]) if expected_laws else "（无特定法律需引用）"
    human_text = (
        f"## 投诉信内容\n{complaint_letter}\n\n"
        f"## 引用的法律依据\n{json.dumps(result.get('legal_basis', []), ensure_ascii=False)}\n\n"
        f"## 应引用的法律依据\n{expected_laws_text}\n\n"
        f"请对以上投诉信进行质量审查。"
    )

    review = llm.chat_json_data(system_prompt, human_text, temperature=0.1, max_tokens=2048, fallback=None, model=settings.llm_fast_model)
    if not review:
        return result

    if not review.get("passed", True):
        improved_letter = review.get("improved_letter", "")
        if improved_letter:
            result["complaint_letter"] = improved_letter
        improved_basis = review.get("improved_legal_basis", [])
        if improved_basis:
            result["legal_basis"] = improved_basis
        suggestions = review.get("suggestions", [])
        if suggestions:
            result["suggestions"] = suggestions
    return result


# ============================================================
#  Step 6: 沟通话术模板
# ============================================================

def _generate_negotiation_script(facts: dict, matched_laws: list) -> dict:
    """LLM 生成与商家/平台/12315 沟通的分步话术"""

    legal_summary = "\n".join([
        f"- 《{law['law_name']}》{law['article']}：{law['content'][:80]}..."
        for law in matched_laws
    ]) if matched_laws else "（无特定法律引用）"

    fact_summary = (
        f"- 平台：{facts.get('platform', '未提及')}\n"
        f"- 商品：{facts.get('product', '未提及')}\n"
        f"- 金额：{facts.get('amount', '未提及')} 元\n"
        f"- 问题：{facts.get('issue_type', '未提及')}\n"
        f"- 描述：{facts.get('issue_description', '')[:100]}...\n"
        f"- 诉求：{facts.get('desired_outcome', '未提及')}"
    )

    system_prompt = (
        "你是一个消费者维权沟通专家。你的任务是根据用户的维权事实，生成一份分步的沟通话术模板，"
        "帮助用户在不同阶段与商家、平台、12315等各方有效沟通。\n\n"
        "话术要求：\n"
        "1. 语气要专业、坚定但不失礼貌\n"
        "2. 每句话都要有具体事实依据（时间、商品、金额、问题）\n"
        "3. 适当引用法律条文增加说服力\n"
        "4. 让普通消费者能直接复制使用\n\n"
        "请严格按照以下 JSON 格式输出，只输出一个 JSON 对象：\n"
        "{\n"
        '    "steps": [\n'
        "        {\"step\": 1, \"title\": \"与商家客服沟通\", \"scenario\": \"适用场景说明\", \"script\": \"完整沟通话术\", \"target\": \"发送给谁\", \"tips\": \"沟通技巧提示\"},\n"
        "        {\"step\": 2, \"title\": \"与平台客服沟通（商家不配合时）\", \"scenario\": \"适用场景说明\", \"script\": \"完整沟通话术\", \"target\": \"发送给谁\", \"tips\": \"沟通技巧提示\"},\n"
        "        {\"step\": 3, \"title\": \"向12315提交投诉\", \"scenario\": \"适用场景说明\", \"script\": \"在12315平台填写时的关键描述\", \"target\": \"全国12315平台\", \"tips\": \"提交技巧提示\"}\n"
        "    ]\n"
        "}"
    )

    human_text = (
        f"## 用户维权事实\n{fact_summary}\n\n## 适用法律依据\n{legal_summary}\n\n"
        f"请根据以上信息，生成分步沟通话术模板。话术中要包含具体的事实信息（不要用占位符），并适当引用法律条文。"
    )

    data = llm.chat_json_data(system_prompt, human_text, temperature=0.2, max_tokens=2048, fallback={"steps": []}, model=settings.llm_fast_model)
    return data if isinstance(data, dict) else {"steps": []}


# ============================================================
#  主入口
# ============================================================

def _ensure_law_cited(letter: str, matched_laws: list) -> str:
    """信函若未引用任何匹配法条，追加一条法律依据（保持官方链接逻辑不变）"""
    if not letter or not matched_laws:
        return letter
    for law in matched_laws:
        if law.get("law_name") and law.get("law_name") in letter:
            return letter
    law = matched_laws[0]
    extra = (
        "\n\n补充法律依据：《%s》%s：本纠纷依据上述条款主张权利，条文原文可通过"
        "国家法律法规数据库（flk.npc.gov.cn）检索核对。" % (law["law_name"], law["article"])
    )
    return letter.rstrip() + extra


def _rule_fallback(raw_text: str, order_info: Optional[dict]) -> dict:
    """终极降级：完全走纯规则管线，保证任何情况下都能返回结果"""
    from .demo import generate_complaint_demo
    logger.warning("LLM 管线整体降级：使用纯规则生成")
    return generate_complaint_demo(raw_text, order_info)


def generate_complaint(raw_text: str, order_info: Optional[dict] = None) -> dict:
    """
    多步生成管线：根据用户口述的维权经历，生成专业投诉信。

    演示模式（无 API Key）时自动走 services/demo.py 纯规则管线。
    LLM 模式下每一步均有降级兜底：某一步失败不会导致整体崩溃，
    会逐级回退到规则实现，最终保证返回结构完整的结果。
    """
    if settings.demo_mode:
        from .demo import generate_complaint_demo
        logger.info("演示模式：使用纯规则生成管线")
        return generate_complaint_demo(raw_text, order_info)

    # ---------- Step 1: 事实提取（LLM → 规则降级） ----------
    try:
        facts = _extract_facts(raw_text, order_info)
        if not facts.get("issue_description"):
            raise ValueError("事实提取结果为空")
    except Exception as e:
        logger.warning("LLM 事实提取失败，降级规则提取：%s", e)
        from .demo import extract_facts as rule_extract
        facts = rule_extract(raw_text, order_info)

    # ---------- Step 2: 法律检索（LLM → 知识库校验 → 规则降级） ----------
    try:
        matched_laws = _validate_matched_laws(_match_laws(facts))
        if not matched_laws:
            raise ValueError("法律匹配为空或未通过校验")
    except Exception as e:
        logger.warning("LLM 法律匹配失败，降级规则匹配：%s", e)
        from .demo import match_laws as rule_match
        matched_laws = rule_match(facts)

    # ---------- Step 3 + Step 6: 信函与话术并行（各自独立降级） ----------
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        letter_future = pool.submit(_generate_complaint_letter, facts, matched_laws)
        script_future = pool.submit(_generate_negotiation_script, facts, matched_laws)

        try:
            result = letter_future.result()
            if not result.get("complaint_letter"):
                raise ValueError("信函为空")
        except Exception as e:
            logger.warning("LLM 信函生成失败，降级规则信函：%s", e)
            from .demo import generate_letter as rule_letter
            result = rule_letter(facts, matched_laws)

        try:
            negotiation_script = script_future.result()
            if not negotiation_script.get("steps"):
                raise ValueError("话术为空")
        except Exception as e:
            logger.warning("LLM 话术生成失败，降级规则话术：%s", e)
            from .demo import generate_negotiation_script as rule_script
            negotiation_script = rule_script(facts, matched_laws)

    # Step 4: 商家资质建议（规则驱动，无 LLM）
    result["merchant_qualification_advice"] = get_merchant_qualification_advice(facts)

    # Step 5: 自我审查（失败不影响结果）
    # 规则初筛通过则跳过模型质检（失败不影响结果）
    try:
        need_review, review_issues = _letter_needs_review(result.get("complaint_letter", ""), facts, matched_laws)
        if settings.llm_always_review or need_review:
            if need_review:
                logger.info("质检触发（规则初筛命中）：%s", "；".join(review_issues))
            result = _self_review(result, facts, matched_laws)
        else:
            logger.info("规则初筛通过，跳过模型质检以降低耗时")
    except Exception as e:
        logger.warning("自我审查失败，保留原结果：%s", e)

    if not result.get("suggestions"):
        missing = facts.get("missing_fields") or []
        result["suggestions"] = (
            [f"建议补充：{item}" for item in missing]
            if missing
            else ["信息完整，可提交至12315平台。建议保留订单截图、支付凭证与聊天记录作为证据。"]
        )

    # 代码级兜底：放在质检之后，质检若重写了文书，同样要过一遍防编造净化
    if result.get("complaint_letter"):
        result["complaint_letter"] = _sanitize_letter(result["complaint_letter"], facts)
        result["complaint_letter"] = _ensure_law_cited(result["complaint_letter"], matched_laws)

    # 补充类别 + 渠道建议
    result["category"] = facts.get("category", "其他")
    result["channel_advice"] = get_channel_advice(facts, matched_laws)

    # 话术结果
    result["negotiation_script"] = negotiation_script

    # 法律依据溯源（法条全文 + 官方来源链接）
    from .legal import build_legal_details
    result["legal_details"] = build_legal_details(matched_laws)

    return result


def generate_complaint_progressive(
    raw_text: str,
    order_info: Optional[dict] = None,
    evidence: Optional[list] = None,
    progress: Optional[Callable] = None,
) -> dict:
    """
    分阶段生成：先快速出骨架，再补全完整文书。
    progress(stage, pct, skeleton) 每次阶段推进时回调，供任务式接口轮询展示。
    演示模式瞬间完成；LLM 模式下每一步均有规则降级兜底。
    """

    def pub(stage: str, pct: float, skeleton: str = ""):
        if progress:
            try:
                progress(stage, pct, skeleton)
            except Exception:
                pass

    if settings.demo_mode:
        from .demo import generate_complaint_demo
        result = generate_complaint_demo(raw_text, order_info)
        result.setdefault("category", "其他")
        result.setdefault("negotiation_script", {"steps": []})
        result.setdefault("merchant_qualification_advice", {"items": []})
        result.setdefault("suggestions", [])
        if not result.get("legal_details"):
            from .legal import build_legal_details
            result["legal_details"] = build_legal_details([])
        pub("已完成（演示模式）", 1.0, result.get("complaint_letter", ""))
        return result

    # ---------- Step 1 ∥ Step 2: 事实提取与法律匹配并行 ----------
    from concurrent.futures import ThreadPoolExecutor
    pub("正在梳理维权要点并匹配法律", 0.15)
    # 法律检索只依赖用户原话（不依赖结构化事实），因此与事实提取并行执行，
    # 把两次模型调用的等待重叠起来。
    with ThreadPoolExecutor(max_workers=2) as pool:
        facts_future = pool.submit(_extract_facts, raw_text, order_info)
        laws_future = pool.submit(_match_laws, {"issue_description": raw_text[:300]}, raw_text)

        # ---------- Step 1: 事实提取 ----------
        try:
            facts = facts_future.result()
            if not facts.get("issue_description"):
                raise ValueError("事实提取结果为空")
        except Exception as e:
            logger.warning("LLM 事实提取失败，降级规则提取：%s", e)
            from .demo import extract_facts as rule_extract
            facts = rule_extract(raw_text, order_info)

        # ---------- Step 2: 法律匹配 ----------
        try:
            matched_laws = _validate_matched_laws(laws_future.result())
            if not matched_laws:
                raise ValueError("法律匹配为空或未通过校验")
        except Exception as e:
            logger.warning("LLM 法律匹配失败，降级规则匹配：%s", e)
            from .demo import match_laws as rule_match
            matched_laws = rule_match(facts)
    pub("法律条文已匹配", 0.30)

    # ---------- Step 3b ∥ Step 3 ∥ Step 6: 骨架 / 完整文书 / 话术 三路并行 ----------
    # 骨架只是为了让用户早点看到内容，不必等它完成再开文书，所以一起提交。
    pub("正在起草投诉信骨架", 0.42)
    with ThreadPoolExecutor(max_workers=3) as pool:
        skeleton_future = pool.submit(_generate_skeleton, facts, matched_laws)
        letter_future = pool.submit(_generate_complaint_letter, facts, matched_laws)
        script_future = pool.submit(_generate_negotiation_script, facts, matched_laws)

        try:
            skeleton = skeleton_future.result() or ""
            if skeleton:
                pub("投诉信骨架已生成", 0.55, skeleton)
        except Exception as e:
            logger.warning("骨架生成失败（不影响完整文书）：%s", e)

        pub("正在生成完整文书", 0.62)

        try:
            result = letter_future.result()
            if not result.get("complaint_letter"):
                raise ValueError("信函为空")
        except Exception as e:
            logger.warning("LLM 信函生成失败，降级规则信函：%s", e)
            from .demo import generate_letter as rule_letter
            result = rule_letter(facts, matched_laws)

        try:
            negotiation_script = script_future.result()
            if not negotiation_script.get("steps"):
                raise ValueError("话术为空")
        except Exception as e:
            logger.warning("LLM 话术生成失败，降级规则话术：%s", e)
            from .demo import generate_negotiation_script as rule_script
            negotiation_script = rule_script(facts, matched_laws)

    # Step 4: 商家资质建议（规则驱动）
    result["merchant_qualification_advice"] = get_merchant_qualification_advice(facts)

    # ---------- Step 5: 自我审查 ----------
    # 规则初筛通过则跳过模型质检：省下一次 10 秒级的模型调用，保证大多数请求更快

    try:
        need_review, review_issues = _letter_needs_review(result.get("complaint_letter", ""), facts, matched_laws)
        if settings.llm_always_review or need_review:
            if need_review:
                logger.info("质检触发（规则初筛命中）：%s", "；".join(review_issues))
            pub("正在质检并优化文书", 0.80)
            result = _self_review(result, facts, matched_laws)
        else:
            logger.info("规则初筛通过，跳过模型质检以降低耗时")
    except Exception as e:
        logger.warning("自我审查失败，保留原结果：%s", e)

    # 跳过质检时，建议项由缺失字段生成（与规则管线保持一致）
    if not result.get("suggestions"):
        missing = facts.get("missing_fields") or []
        result["suggestions"] = (
            [f"建议补充：{item}" for item in missing]
            if missing
            else ["信息完整，可提交至12315平台。建议保留订单截图、支付凭证与聊天记录作为证据。"]
        )

    # 代码级兜底：放在质检之后，质检若重写了文书，同样要过一遍防编造净化
    if result.get("complaint_letter"):
        result["complaint_letter"] = _sanitize_letter(result["complaint_letter"], facts)
        result["complaint_letter"] = _ensure_law_cited(result["complaint_letter"], matched_laws)
    result["category"] = facts.get("category", "其他")
    result["channel_advice"] = get_channel_advice(facts, matched_laws)
    result["negotiation_script"] = negotiation_script

    from .legal import build_legal_details
    result["legal_details"] = build_legal_details(matched_laws)

    pub("完成", 1.0, result.get("complaint_letter", ""))
    return result
