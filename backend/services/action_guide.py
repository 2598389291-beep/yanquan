"""维权行动清单：把「下一步做什么」变成用户照做的分步动作（纯规则，不依赖大模型）

核心思路：用户不是缺一封信，而是缺「每一步具体怎么做」。
"""

from .evidence_checklist import CATEGORY_TO_SCENARIO, get_evidence_checklist



# ============ 路径推荐：帮用户做判断，而不是给选项 ============

PATH_RECOMMENDATIONS = {
    "网购纠纷": {
        "recommended": "12315 投诉",
        "reason": "网购纠纷由市监部门受理调解，受理后有明确时限，退货退款类诉求通过率较高",
        "backup": "若商家 7 天内不理会，转黑猫投诉公开曝光施压",
    },
    "产品质量": {
        "recommended": "12315 投诉",
        "reason": "质量问题适用三包/退换规定，12315 受理后可按证据组织调解",
        "backup": "若商家 7 天内不理会，转黑猫投诉公开曝光施压",
    },
    "食品安全": {
        "recommended": "12315 投诉 + 举报",
        "reason": "食品安全问题可主张退一赔十，12315 受理率最高；同时勾选「举报」可触发行政立案，威慑力强",
        "backup": "若商家 7 天内不理会，保留物证并同步向属地市场监管部门书面举报",
    },
    "虚假宣传": {
        "recommended": "12315 投诉 + 举报",
        "reason": "虚假宣传可能构成欺诈（退一赔三），举报会让平台与商家更重视",
        "backup": "若商家 7 天内不理会，转黑猫投诉公开曝光，并保留直播回放/宣传截图",
    },
    "服务纠纷": {
        "recommended": "12315 投诉",
        "reason": "服务/预付卡纠纷属市监职责范围，受理后组织调解；预付卡可同时向商务部门反映",
        "backup": "若商家 7 天内不理会，转黑猫投诉曝光，并准备诉讼材料",
    },
    "价格欺诈": {
        "recommended": "12315 投诉 + 举报",
        "reason": "价格欺诈属于行政处罚范围，举报比单纯投诉更容易促成退款",
        "backup": "若商家 7 天内不理会，转黑猫投诉公开曝光",
    },
    "合同纠纷": {
        "recommended": "12315 投诉（协商阶段）",
        "reason": "合同争议先走调解成本最低；金额明确、证据齐全时可直接准备小额诉讼",
        "backup": "调解不成或商家失联 → 小额诉讼（费用低、一审终审，不依赖商家配合）",
    },
    "其他": {
        "recommended": "12315 投诉",
        "reason": "绝大多数消费纠纷都归市监部门受理，先走官方渠道最稳妥",
        "backup": "若商家 7 天内不理会，转黑猫投诉公开曝光施压",
    },
}

UPGRADE_PLAN = [
    {"step": 1, "action": "商家 7 天不回应 → 升级 12315 行政投诉", "detail": "在 12315 原投诉单上追加「已超期未处理」并附上沟通记录；行政投诉有法定期限义务，处理更有约束力"},
    {"step": 2, "action": "金额明确、证据齐全 → 考虑小额诉讼", "detail": "小额诉讼费用很低（常见约 50 元起）、一审终审，不需要商家配合，法院缺席也能判；适合金额 1 万元以下的简单纠纷"},
    {"step": 3, "action": "公开曝光施压（可选）", "detail": "在黑猫投诉发布完整事实与证据，公开信息会促使商家为名誉快速处理"},
]

# 动态匹配渠道：按纠纷类型给出对口部门及理由
MATCHED_CHANNELS = {
    "食品安全": [{"name": "全国12315平台", "kind": "小程序", "search": "全国12315平台", "url": "https://www.12315.cn/", "phone": "12315", "reason": "食品安全退一赔十，受理率最高"}],
    "快递": [{"name": "国家邮政局申诉网站", "kind": "官网", "search": "国家邮政局申诉网站", "url": "https://sswz.spb.gov.cn/", "phone": "12305", "reason": "快递问题归邮政部门管，申诉比 12315 更快更对口"}],
    "电信": [{"name": "工信部电信用户申诉受理中心", "kind": "官网", "search": "工信部申诉受理", "url": "https://yhssglxt.miit.gov.cn/", "phone": "12300", "reason": "运营商扣费/套餐争议归工信部门受理"}],
    "预付卡": [{"name": "全国12315平台", "kind": "小程序", "search": "全国12315平台", "url": "https://www.12315.cn/", "phone": "12315", "reason": "预付卡退费归市监受理，可同步向商务部门反映"}],
}

# 类别 → 动态渠道 key（食品/快递/电信/预付卡按类别特化；其余返回空走通用推荐）
CATEGORY_TO_CHANNEL_KEY = {
    "网购纠纷": None, "产品质量": None, "食品安全": "食品安全",
    "虚假宣传": None, "服务纠纷": None, "价格欺诈": None,
    "合同纠纷": None, "其他": None,
}


def build_path_recommendation(category: str) -> dict:
    rec = dict(PATH_RECOMMENDATIONS.get(category, PATH_RECOMMENDATIONS["其他"]))
    rec["upgrade_plan"] = UPGRADE_PLAN
    return rec


def build_matched_channels(category: str) -> list:
    key = CATEGORY_TO_CHANNEL_KEY.get(category)
    return MATCHED_CHANNELS.get(key, []) if key else []


def build_action_checklist(category: str = "其他") -> list:
    """按纠纷类别生成 4-6 步行动清单（步骤 / 说明 / 预计耗时）"""
    steps = [
        {
            "step": 1,
            "action": "立即留存证据",
            "detail": "按证据清单把订单、聊天、支付、物流凭证截图保存好，越全越好",
            "duration": "5 分钟",
        },
        {
            "step": 2,
            "action": "先与商家/平台协商",
            "detail": "把生成的投诉信与证据发给商家或平台客服，明确诉求（退款/换货/赔偿）",
            "duration": "1-3 天",
        },
        {
            "step": 3,
            "action": "协商无果 → 提交 12315",
            "detail": "微信搜索「全国12315平台」小程序，粘贴材料包并附上证据，选择「投诉」；涉嫌违法的同时勾选「举报」",
            "duration": "7 个工作日内受理",
        },
        {
            "step": 4,
            "action": "跟进受理与调解",
            "detail": "保留受理编号，市场监管部门会组织调解；调解不成会告知下一步途径",
            "duration": "一般 30-60 天",
        },
        {
            "step": 5,
            "action": "仍未解决 → 诉讼兜底",
            "detail": "小额纠纷可向法院起诉，小额诉讼程序费用低（常见约 50 元起）、一审终审",
            "duration": "1-3 个月",
        },
    ]

    # 按类别插入特定通道，让清单更贴近场景
    if category == "食品安全":
        steps.insert(1, {
            "step": 0,
            "action": "封存食品与就医留证",
            "detail": "剩余食品、外包装原样封存，就医保留病历与票据，这是退一赔十的关键",
            "duration": "立即",
        })
    elif category in ("服务纠纷", "合同纠纷"):
        steps[2]["detail"] = "微信搜索「全国12315平台」小程序，粘贴材料包并附合同/缴费/交涉记录；预付卡纠纷可同时向商务主管部门反映"
    elif category == "其他":
        pass

    # 重排序号
    for i, s in enumerate(steps, 1):
        s["step"] = i
    return steps


def attach_action_guide(result: dict) -> dict:
    """给生成结果挂上行动清单 + 证据清单（幂等）"""
    category = result.get("category") or "其他"
    if not result.get("action_checklist"):
        result["action_checklist"] = build_action_checklist(category)
    if not result.get("evidence_checklist"):
        result["evidence_checklist"] = get_evidence_checklist(CATEGORY_TO_SCENARIO.get(category, "general"))
    if not result.get("path_recommendation"):
        result["path_recommendation"] = build_path_recommendation(category)
    if not result.get("matched_channels"):
        result["matched_channels"] = build_matched_channels(category)
    return result
