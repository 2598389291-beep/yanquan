"""演示模式：纯规则生成管线（无需任何外部 API）

当未配置 DASHSCOPE_API_KEY 时自动启用，保证项目开箱即可演示：
- 规则事实提取（金额 / 平台 / 类别 / 诉求）
- 标签匹配法律知识库
- 模板化投诉信 / 话术 / 维权路径
"""

import re
from typing import Optional

from ..database import get_legal_knowledge
from .advice import get_channel_advice, get_merchant_qualification_advice

# ============ 关键词表 ============

PLATFORM_KEYWORDS = {
    "拼多多": ["拼多多", "pdd"],
    "淘宝": ["淘宝", "天猫", "tb"],
    "京东": ["京东", "jd"],
    "美团": ["美团", "外卖"],
    "抖音": ["抖音", "直播间"],
    "快手": ["快手"],
    "闲鱼": ["闲鱼"],
    "饿了么": ["饿了么", "饿了吗"],
    "小红书": ["小红书"],
    "唯品会": ["唯品会"],
    "携程": ["携程", "飞猪", "去哪儿", "同程"],
    "微信": ["微信", "微商", "小程序"],
}

CATEGORY_KEYWORDS = [
    (["假货", "货不对板", "假冒", "仿品", "盗版", "高仿"], "网购纠纷", "假货/货不对板"),
    (["质量", "坏了", "破损", "故障", "损坏", "不灵", "漏水", "开裂", "变质", "生锈"], "产品质量", "质量问题"),
    (["食品", "外卖", "吃出", "蟑螂", "头发", "苍蝇", "异物", "腹泻", "变质", "过期"], "食品安全", "食品安全"),
    (["虚假宣传", "夸大", "宣传不符", "广告", "主播说", "承诺", "效果"], "虚假宣传", "虚假宣传"),
    (["价格欺诈", "乱收费", "涨价", "虚标", "多扣", "乱扣", "扣费"], "价格欺诈", "价格欺诈"),
    (["合同", "违约", "不退定金", "不履行", "跑路", "关门", "失联"], "合同纠纷", "合同违约"),
    (["快递", "丢件", "物流", "没收到", "破损", "延迟"], "服务纠纷", "快递/物流纠纷"),
    (["退款", "退货", "换货", "不处理", "客服", "态度"], "服务纠纷", "售后纠纷"),
]

OUTCOME_KEYWORDS = [
    (["退一赔三", "三倍赔偿", "三倍", "假一赔三"], "退货退款并依法要求三倍赔偿（退一赔三）"),
    (["退一赔十", "十倍赔偿", "十倍", "1000元赔偿", "一千元"], "退货退款并依法要求十倍赔偿（退一赔十）"),
    (["赔偿", "损失"], "退款并赔偿相应损失"),
    (["退款", "退钱", "退费"], "全额退款"),
    (["换货"], "更换同款合格商品"),
    (["道歉"], "要求商家/平台书面道歉"),
]

ISSUE_MAP = {
    "假货/货不对板": "商品为假冒伪劣、货不对板",
    "质量问题": "商品存在质量问题",
    "食品安全": "食品存在安全隐患",
    "虚假宣传": "商家涉嫌虚假宣传",
    "价格欺诈": "商家涉嫌价格欺诈",
    "合同违约": "商家未按约定履行合同义务",
    "快递/物流纠纷": "快递/物流环节出现纠纷",
    "售后纠纷": "售后处理不当、拒绝履行售后义务",
    "其他": "消费权益受损",
}


# ============ Step 1: 规则事实提取 ============

def extract_facts(raw_text: str, order_info: Optional[dict] = None) -> dict:
    text = raw_text or ""

    # 金额
    amount = ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*元", text)
    if m:
        amount = m.group(1)
    elif order_info and order_info.get("amount"):
        amount = str(order_info["amount"])

    # 平台
    platform = ""
    for name, kws in PLATFORM_KEYWORDS.items():
        if any(kw in text for kw in kws):
            platform = name
            break
    if order_info and order_info.get("platform") and not platform:
        platform = order_info["platform"]

    # 商家（"XX店"、"XX公司"等）
    seller = ""
    m = re.search(r"(?:在|从|向)?([\u4e00-\u9fa5A-Za-z0-9]{2,24}?)(?:店铺|旗舰店|专卖店|商家|公司|商家处|卖家)", text)
    if m:
        seller = m.group(1)
    if order_info and order_info.get("seller") and not seller:
        seller = order_info["seller"]

    # 商品（关键词 heuristic：名词 + 购买对象）
    product = ""
    if order_info and order_info.get("product_name"):
        product = order_info["product_name"]
    if not product:
        m = re.search(r"(?:买了|购买|订了|点了|充值|办了)(.{2,18}?)(?:，|。|,|花了|用了|收到|结果|但是|发现|一共|价格)", text)
        if m:
            product = m.group(1).strip()

    # 时间
    issue_date = ""
    m = re.search(r"((?:20\d{2}|去年|今年|上个月|这个月|昨天|前天|上周|最近)[^\s，。]{0,12}?(?:月|日|号|天))", text)
    if m:
        issue_date = m.group(1)
    if order_info and order_info.get("order_date") and not issue_date:
        issue_date = order_info["order_date"]

    # 类别 + 问题类型
    category = "其他"
    issue_type = "其他"
    for kws, cat, typ in CATEGORY_KEYWORDS:
        if any(kw in text for kw in kws):
            category, issue_type = cat, typ
            break

    # 诉求
    desired_outcome = ""
    for kws, outcome in OUTCOME_KEYWORDS:
        if any(kw in text for kw in kws):
            desired_outcome = outcome
            break
    if not desired_outcome:
        if any(kw in text for kw in ["退一赔三", "三倍"]):
            desired_outcome = "退货退款并依法要求三倍赔偿（退一赔三）"
        elif any(kw in text for kw in ["退一赔十", "十倍"]):
            desired_outcome = "退货退款并依法要求十倍赔偿（退一赔十）"
        else:
            desired_outcome = "依法退货退款"

    # 缺失信息
    missing_fields = []
    if not amount:
        missing_fields.append("未提及具体金额（投诉信中将标注[请补充]）")
    if not issue_date:
        missing_fields.append("未提及购买/事发时间（投诉信中将标注[请补充]）")
    if not seller:
        missing_fields.append("未提及商家名称（投诉信中将标注[请补充]）")
    if not platform:
        missing_fields.append("未提及购买平台（投诉信中将标注[请补充]）")

    facts = {
        "platform": platform,
        "product": product,
        "amount": amount,
        "issue_date": issue_date,
        "seller": seller,
        "issue_type": issue_type,
        "issue_description": text,
        "desired_outcome": desired_outcome,
        "missing_fields": missing_fields,
        "category": category,
    }
    if order_info:
        facts["order_info"] = order_info
    return facts


# ============ Step 2: 规则法律匹配 ============

def match_laws(facts: dict) -> list:
    """基于知识库标签 + 文本关键词的规则匹配"""
    # 场景 → 优先法律（演示模式精确匹配兜底，避免多法条并列时选错）
    PRIORITY_LAWS = {
        "虚假宣传": ["广告法", "反不正当竞争法"],
        "食品安全": ["食品安全法"],
        "快递": ["快递暂行条例"],
        "物流": ["快递暂行条例"],
        "预付卡": ["单用途商业预付卡管理办法（试行）"],
        "自动续费": ["消费者权益保护法实施条例", "网络交易监督管理办法"],
        "电信": ["电信条例"],
        "汽车": ["家用汽车产品修理更换退货责任规定"],
        "化妆品": ["化妆品监督管理条例"],
        "七天无理由": ["网络购买商品七日无理由退货暂行办法"],
        "直播": ["网络交易监督管理办法", "广告法"],
    }
    text = "".join([
        facts.get("issue_type", ""), facts.get("category", ""),
        facts.get("issue_description", ""), facts.get("desired_outcome", ""),
    ])
    all_laws = get_legal_knowledge()
    for keyword, laws in PRIORITY_LAWS.items():
        if keyword in text:
            for law in laws:
                for row in all_laws:
                    if row["law_name"].startswith(law):
                        row["_priority"] = 10
            break
    scored = []
    for law in all_laws:
        tags = law.get("tags", "[]")
        if isinstance(tags, str):
            import json
            tags = json.loads(tags)
        score = 0
        for tag in tags:
            if tag in text:
                score += 1
        score += int(law.get("_priority", 0))
        if score > 0:
            scored.append((score, law))
    scored.sort(key=lambda x: -x[0])
    return [law for _, law in scored[:3]]


# ============ Step 3: 规则投诉信生成 ============

def generate_letter(facts: dict, matched_laws: list) -> dict:
    category = facts.get("category", "其他")
    issue = ISSUE_MAP.get(facts.get("issue_type", "其他"), "消费权益受损")
    platform = facts.get("platform") or "[请补充购买平台]"
    seller = facts.get("seller") or "[请补充商家名称]"
    product = facts.get("product") or "[请补充商品/服务名称]"
    amount = facts.get("amount") or "[请补充具体金额]"
    issue_date = facts.get("issue_date") or "[请补充购买/事发时间]"
    desired_outcome = facts.get("desired_outcome") or "依法退货退款"
    description = facts.get("issue_description", "").strip()

    laws_text = "\n".join(
        [f"《{law['law_name']}》{law['article']}：{law['content']}" for law in matched_laws]
    ) or "（依据《中华人民共和国消费者权益保护法》等法律法规）"

    legal_basis = [f"{law['law_name']} {law['article']}" for law in matched_laws]
    if not legal_basis:
        legal_basis = ["消费者权益保护法 第24条"]

    amount_text = f"{amount}元" if amount and amount != "[请补充具体金额]" else amount
    amount_demand = ""
    if amount and amount != "[请补充具体金额]":
        amount_demand = f"，合计金额{amount}元"

    letter = f"""投诉信

被投诉方：{seller}
投诉平台：{platform}

一、投诉事由
本人于{issue_date}在{platform}购买{product}，金额为{amount_text}。使用/收货过程中发现{issue}，具体经过如下：

二、事实经过
{description}

三、法律依据
依据以上事实，本人认为被投诉方的行为已违反以下法律法规：
{laws_text}

四、投诉诉求
1. 要求被投诉方立即{desired_outcome}；
2. 对本次纠纷给出书面处理结果及处理时限；
3. 依据相关法律规定，如被投诉方拒不处理，本人保留向市场监督管理部门投诉举报、并通过消费保/黑猫投诉等公开渠道曝光，以及向人民法院提起诉讼的权利。

特此投诉，望贵方尽快核实处理。{amount_demand}

投诉人：（请填写您的姓名）
联系电话：（请填写您的手机号）"""

    # 维权路径
    action_path = []
    step = 1
    if facts.get("platform"):
        action_path.append({
            "step": step,
            "action": f"联系{platform}官方客服",
            "detail": f"在{platform}App中找到订单，点击「申请售后/投诉商家」，描述问题并上传证据，要求平台介入协调。（预计1-3个工作日）",
        })
        step += 1
    action_path.append({
        "step": step,
        "action": "向 12315 平台提交投诉",
        "detail": "打开微信搜索「全国12315平台」小程序，选择投诉，填写被投诉企业全称与投诉事由（可直接粘贴本投诉信）。市场监管部门应在7个工作日内决定是否受理。（预计7-45天）",
    })
    step += 1
    action_path.append({
        "step": step,
        "action": "多渠道曝光施压",
        "detail": "若商家仍不处理，可将投诉信同步发布至黑猫投诉平台，借助公开曝光机制施加舆论压力。",
    })
    step += 1
    if facts.get("amount"):
        try:
            amount_num = float(facts["amount"])
            if amount_num > 1000:
                action_path.append({
                    "step": step,
                    "action": "向人民法院提起诉讼",
                    "detail": "金额超过1000元可考虑小额诉讼程序，一审终审、费用低、速度快；也可先拨打12348法律援助热线咨询。",
                })
        except ValueError:
            pass

    return {
        "complaint_letter": letter,
        "legal_basis": legal_basis,
        "action_path": action_path,
    }


# ============ Step 4: 规则话术模板 ============

def generate_negotiation_script(facts: dict, matched_laws: list) -> dict:
    platform = facts.get("platform") or "购买平台"
    seller = facts.get("seller") or "贵店"
    product = facts.get("product") or "所购商品"
    amount = facts.get("amount") or ""
    issue = ISSUE_MAP.get(facts.get("issue_type", "其他"), "消费权益受损")
    laws = "、".join([f"《{law['law_name']}》{law['article']}" for law in matched_laws]) or "《中华人民共和国消费者权益保护法》"
    amount_part = f"，金额为{amount}元" if amount else ""

    steps = [
        {
            "step": 1,
            "title": "与商家客服沟通",
            "scenario": "首先通过平台聊天工具联系商家，正式提出诉求",
            "target": f"{platform}商家客服",
            "script": f"您好，我在贵店购买的{product}{amount_part}，{issue}。根据{laws}，我要求{facts.get('desired_outcome', '依法退货退款')}。请于48小时内给出处理方案，否则我将向12315平台投诉并保留进一步维权权利。",
            "tips": "沟通时保留聊天记录截图；不要使用过激言辞，聚焦事实与诉求。",
        },
        {
            "step": 2,
            "title": "升级到平台官方客服",
            "scenario": "商家不配合或拖延时，联系平台官方客服要求介入",
            "target": f"{platform}官方客服",
            "script": f"我于近日在贵平台购买{product}{amount_part}，{issue}。商家拒绝处理，违反了《电子商务法》第38条关于平台审核与协助义务的规定。请平台介入处理，要求商家{facts.get('desired_outcome', '依法退货退款')}，否则我将向12315投诉贵平台未尽到管理义务。",
            "tips": "强调平台责任条款，平台通常更重视合规风险，会加快处理。",
        },
        {
            "step": 3,
            "title": "提交12315投诉",
            "scenario": "商家与平台均未解决时，正式提交行政投诉",
            "target": "全国12315平台",
            "script": f"本人于{platform}购买{product}{amount_part}，{issue}。与商家、平台多次沟通无果，现依据{laws}正式投诉，要求商家{facts.get('desired_outcome', '依法退货退款')}，并请求市场监管部门依法处理。",
            "tips": "填写时选择「投诉」而非「举报」解决个人纠纷；如涉食品安全、虚假宣传等违法行为，可同时提交举报。",
        },
    ]
    return {"steps": steps}


# ============ 主入口 ============

def generate_complaint_demo(raw_text: str, order_info: Optional[dict] = None) -> dict:
    """纯规则演示管线，返回与 LLM 管线完全一致的结构"""
    facts = extract_facts(raw_text, order_info)
    matched_laws = match_laws(facts)
    result = generate_letter(facts, matched_laws)

    # 法律依据溯源（法条全文 + 官方来源链接）
    from .legal import build_legal_details
    result["legal_details"] = build_legal_details(matched_laws)

    result["category"] = facts.get("category", "其他")
    result["merchant_qualification_advice"] = get_merchant_qualification_advice(facts)
    result["channel_advice"] = get_channel_advice(facts, matched_laws)
    result["negotiation_script"] = generate_negotiation_script(facts, matched_laws)

    if facts.get("missing_fields"):
        result["suggestions"] = [f"建议补充：{item}" for item in facts["missing_fields"]]
    else:
        result["suggestions"] = ["信息完整，可提交至12315平台。建议保留订单截图、支付凭证与聊天记录作为证据。"]

    return result
