"""维权路径决策矩阵：告诉用户「你现在什么情况 → 该走哪条路」（规则数据，不依赖大模型）"""

_BASE = [
    {
        "channel": "与商家/平台协商",
        "when": "问题刚发生、商家态度正常时优先尝试，成本最低",
        "duration": "1-3 天",
        "cost": "0 元",
        "next": "商家拒绝或拖延 → 走 12315",
    },
    {
        "channel": "12315 投诉 / 举报",
        "when": "协商无果；或涉嫌欺诈、食品安全、虚假宣传等违法行为",
        "duration": "7 个工作日内受理，调解一般 30-60 天",
        "cost": "0 元",
        "next": "调解失败 → 消协调解或起诉",
    },
    {
        "channel": "消费者协会调解",
        "when": "希望有人出面调解、不想对簿公堂",
        "duration": "通常 1-2 个月",
        "cost": "0 元",
        "next": "调解不成 → 起诉",
    },
    {
        "channel": "法院起诉（小额诉讼）",
        "when": "金额明确、证据齐全、其他途径未解决；小额诉讼一审终审",
        "duration": "1-3 个月",
        "cost": "诉讼费低，小额常见 50 元起",
        "next": "判决后仍不履行 → 申请强制执行",
    },
]

# 场景特化：第三通道替换为更对口的部门
_SCENARIO_CHANNEL3 = {
    "express_loss": {
        "channel": "国家邮政局申诉",
        "when": "快递丢失/破损，快递公司内部投诉处理不满意",
        "duration": "一般 7-15 天",
        "cost": "0 元",
        "next": "仍不处理 → 起诉",
    },
    "telecom": {
        "channel": "工信部电信用户申诉",
        "when": "运营商乱扣费/套餐争议，客服处理不满意",
        "duration": "一般 2-4 周",
        "cost": "0 元",
        "next": "仍不处理 → 起诉",
    },
    "auto_renewal": {
        "channel": "12315 投诉 + 平台所在地消协",
        "when": "自动续费未显著提醒被扣款",
        "duration": "1-4 周",
        "cost": "0 元",
        "next": "不退款 → 起诉",
    },
}


def build_decision(scenario_key: str) -> list:
    channels = [dict(c) for c in _BASE]
    if scenario_key in _SCENARIO_CHANNEL3:
        channels[2] = dict(_SCENARIO_CHANNEL3[scenario_key])
    return channels
