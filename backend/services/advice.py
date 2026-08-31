"""规则驱动的维权建议模块（无需 LLM）：
- 渠道建议（投诉/举报/诉讼/平台协商）
- 商家资质查验建议
"""


def get_channel_advice(facts: dict, matched_laws: list) -> dict:
    """
    根据事实和法律依据，自动判断投诉/举报/诉讼路径。

    返回结构化数据：{channels: [...], summary: "..."}
    """
    category = facts.get("category", "")
    issue_type = facts.get("issue_type", "")
    amount_str = facts.get("amount", "")
    desired_outcome = facts.get("desired_outcome", "")

    try:
        amount = float(amount_str) if amount_str else 0
    except ValueError:
        amount = 0

    law_names = [law["law_name"] for law in matched_laws]

    channels = []
    summary_parts = []
    search_text = issue_type + category + desired_outcome

    # ===== 12315 投诉 =====
    has_personal_loss = any(
        kw in search_text for kw in
        ["退款", "退货", "换货", "质量", "假货", "欺诈", "破损", "不退款", "服务差",
         "食品安全", "食品", "合同违约", "违约", "合同", "快递", "丢件", "物流",
         "预付卡", "跑路", "虚假宣传", "假一赔"]
    )
    if has_personal_loss:
        complaint_laws = [n for n in law_names if "消费者权益保护法" in n or "产品质量法" in n]
        channels.append({
            "channel": "12315 投诉",
            "type": "投诉",
            "reason": "要求商家退还货款/赔偿个人损失",
            "legal_basis": complaint_laws[0] if complaint_laws else "《消费者权益保护法》",
            "priority": 1,
            "action": "通过全国12315平台（网站/App/小程序）提交投诉，要求商家承担相应责任",
        })

    # ===== 12315 举报 =====
    is_illegal = any(
        kw in search_text for kw in
        ["食品安全", "虚假宣传", "广告", "价格欺诈", "刷单", "三无产品", "无资质", "假货"]
    )
    if is_illegal:
        report_laws = [n for n in law_names if "食品安全法" in n or "广告法" in n or "价格法" in n or "反不正当竞争法" in n]
        channels.append({
            "channel": "12315 举报",
            "type": "举报",
            "reason": "涉及商家违法行为，可要求市场监管部门对其进行行政处罚",
            "legal_basis": report_laws[0] if report_laws else "《市场监督管理投诉举报处理暂行办法》",
            "priority": 2 if has_personal_loss else 1,
            "action": "通过全国12315平台提交举报，附上相关证据截图，要求市场监管部门查处",
        })

    # ===== 法院起诉 =====
    if amount > 5000:
        lawsuit_laws = [n for n in law_names if "民法典" in n]
        channels.append({
            "channel": "法院起诉",
            "type": "诉讼",
            "reason": f"涉及金额较大（{int(amount)}元），投诉无效后可考虑通过法律途径解决",
            "legal_basis": lawsuit_laws[0] if lawsuit_laws else "《民法典》",
            "priority": 3,
            "action": "向被告所在地或合同履行地人民法院提起诉讼，金额较小可申请小额诉讼程序（一审终审，费用低、速度快）",
        })
    elif amount > 1000:
        lawsuit_laws = [n for n in law_names if "民法典" in n]
        channels.append({
            "channel": "法院起诉",
            "type": "诉讼",
            "reason": f"涉及金额{int(amount)}元，如12315投诉后商家仍不处理，可考虑起诉",
            "legal_basis": lawsuit_laws[0] if lawsuit_laws else "《民法典》",
            "priority": 4,
            "action": "如投诉无效，向法院提起小额诉讼（标的额较小，程序简单、费用低）",
        })

    # ===== 平台客服协商 =====
    has_platform = any(
        kw in search_text for kw in
        ["网购", "平台", "外卖", "打车", "订票", "淘宝", "拼多多", "京东", "美团", "抖音"]
    ) or bool(facts.get("platform"))
    if has_platform:
        channels.append({
            "channel": "平台客服协商",
            "type": "协商",
            "reason": "先联系购买平台（如淘宝、拼多多、京东等）的官方客服，要求平台介入处理",
            "legal_basis": "《电子商务法》第38条" if "电子商务法" in law_names else "通用维权流程",
            "priority": 0,
            "action": "在平台App内找到订单 → 点击「申请售后/投诉商家」 → 描述问题并上传证据 → 要求平台客服介入协调",
        })

    channels.sort(key=lambda c: c["priority"])

    if channels:
        channel_names = [c["channel"] for c in channels]
        summary_parts.append(f"根据您的维权情况，建议按以下顺序处理：{' → '.join(channel_names)}。")

    return {
        "channels": channels,
        "summary": "。".join(summary_parts) if summary_parts else "",
    }


def get_merchant_qualification_advice(facts: dict) -> dict:
    """
    根据用户维权信息，提供查商家资质的建议（规则驱动，无需 LLM）。

    返回: {merchant_name, items: [...], summary}
    """
    category = facts.get("category", "")
    issue_type = facts.get("issue_type", "")
    seller = facts.get("seller") or "该商家"
    platform = facts.get("platform", "")
    search_text = issue_type + category

    items = []

    # 1. 营业执照（通用）
    items.append({
        "qualification": "营业执照",
        "how_to_check": "要求商家出示营业执照，或通过国家企业信用信息公示系统（https://www.gsxt.gov.cn）查询。如果是在电商平台购物，可在店铺页面查看商家资质信息。",
        "importance": "营业执照是合法经营的基本凭证，商家无证经营本身就是违法行为，可向市场监管部门举报。",
        "red_flag": "如果商家无法提供营业执照，或执照上的经营范围与所售商品/服务不符，说明商家可能无证经营或超范围经营。",
    })

    # 2. 食品经营许可证
    is_food = any(kw in search_text for kw in ["食品", "餐饮", "外卖", "零食", "生鲜"])
    if is_food:
        items.append({
            "qualification": "食品经营许可证",
            "how_to_check": "要求商家出示食品经营许可证，或通过国家市场监督管理总局官网查询。外卖平台商家通常在商家信息页面展示许可证编号。",
            "importance": "食品经营许可证是从事食品销售/餐饮服务的必备资质，无证经营食品可依据《食品安全法》第122条处以5万元以上罚款。",
            "red_flag": "如果商家无法提供食品经营许可证，或许可证已过期，可向12315举报其无证经营。",
        })

    # 3. 化妆品注册/备案
    is_cosmetic = any(kw in search_text for kw in ["化妆品", "护肤品", "美容", "彩妆", "防晒"])
    if is_cosmetic:
        items.append({
            "qualification": "化妆品注册/备案信息",
            "how_to_check": "通过国家药监局官网（https://www.nmpa.gov.cn）或\"化妆品监管\"App查询产品注册/备案信息。正规化妆品应有注册证号或备案编号。",
            "importance": "特殊化妆品需注册，普通化妆品需备案。无注册/备案的产品属于违法违规产品，可要求退一赔三。",
            "red_flag": "如果产品无法查询到注册/备案信息，或备案信息与产品不一致，说明该产品可能为三无产品。",
        })

    # 4. 医疗器械注册
    is_medical = any(kw in search_text for kw in ["医疗器械", "口罩", "医美", "仪器", "检测"])
    if is_medical:
        items.append({
            "qualification": "医疗器械注册证/备案凭证",
            "how_to_check": "通过国家药监局官网查询医疗器械注册/备案信息。正规医疗器械产品包装上应有注册证编号。",
            "importance": "医疗器械分为三类管理，无注册证的产品属于违法产品，可向药监部门举报。",
            "red_flag": "产品包装上无医疗器械注册证号，或注册证号查询不到，则产品来源可疑。",
        })

    # 5. 办学许可证 / 旅行社资质
    if "教育培训" in category or any(kw in search_text for kw in ["培训", "课程", "教育"]):
        items.append({
            "qualification": "办学许可证 / 教育培训资质",
            "how_to_check": "通过当地教育局官网或教育部门查询机构的办学许可证信息。培训机构应在显著位置公示办学许可证。",
            "importance": "从事教育培训需取得办学许可证，无证办学属于违法行为，可向教育部门举报。",
            "red_flag": "培训机构无法提供办学许可证，或借用其他机构许可证经营，属于违规办学。",
        })

    if "旅游" in category or any(kw in search_text for kw in ["旅游", "酒店", "机票", "旅行社"]):
        items.append({
            "qualification": "旅行社业务经营许可证",
            "how_to_check": "通过文化和旅游部官网或当地文旅局查询旅行社资质。正规旅行社应在经营场所公示许可证。",
            "importance": "从事旅游业务需取得旅行社业务经营许可证，无证经营可处1万元以上10万元以下罚款。",
            "red_flag": "旅行社无法提供许可证，或实际经营者与许可证不一致，存在风险。",
        })

    # 6. 3C 认证
    is_electronics = any(kw in search_text for kw in ["充电器", "手机", "电脑", "电器", "电子", "数码", "家电"])
    if is_electronics:
        items.append({
            "qualification": "CCC强制性产品认证（3C认证）",
            "how_to_check": "通过全国认证认可信息公共服务平台（http://cx.cnca.cn）查询3C认证证书。产品包装或说明书上应有CCC标志。",
            "importance": "列入3C目录的产品（如手机、充电器、家电等）必须通过3C认证才能销售，无3C认证属于违法产品。",
            "red_flag": "产品无CCC标志，或CCC证书查询不到/已撤销，说明产品可能不符合安全标准。",
        })

    # 7. 平台商家入驻资质
    if platform:
        items.append({
            "qualification": "平台商家入驻资质",
            "how_to_check": f"在{platform}App中进入该店铺页面，查看\"商家资质\"或\"工商资质\"信息。正规电商平台要求商家上传营业执照、品牌授权等资质方可入驻。",
            "importance": f"平台有义务审核商家资质。如果商家暴露出资质问题，您可以同时投诉{platform}平台未尽审核义务，依据《电子商务法》第38条要求平台承担连带责任。",
            "red_flag": f"商家店铺页面无资质展示入口，或展示的资质与所售商品不符，可向{platform}平台举报并同时向12315投诉。",
        })

    if items:
        names = [item["qualification"] for item in items]
        summary = f"建议您查验商家的以下资质：{'、'.join(names)}。如果商家无法提供上述资质，可将其作为重要证据加入投诉材料，并向12315举报其无证经营或超范围经营。"
    else:
        summary = "当前未检测到特定行业资质要求，建议查验商家的营业执照。如果商家无法提供，可向12315举报。"

    return {"merchant_name": seller, "items": items, "summary": summary}
