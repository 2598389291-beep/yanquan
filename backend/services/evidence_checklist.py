"""证据收集清单：按纠纷场景告诉用户「现在该留哪些证据」（纯规则，不依赖大模型）"""

SCENARIOS = {
    "online": {
        "title": "网购纠纷",
        "icon": "🛒",
        "items": [
            {"item": "订单截图", "purpose": "证明购买时间、平台、金额、商品", "how": "订单详情页截图，含订单号"},
            {"item": "商品页面/宣传截图", "purpose": "证明商家承诺与实物差异", "how": "商品详情、主图、参数页截图"},
            {"item": "聊天记录", "purpose": "证明商家承诺、售后交涉过程", "how": "与客服完整聊天记录（勿只截一段）"},
            {"item": "支付凭证", "purpose": "证明实际付款金额与渠道", "how": "支付账单页截图"},
            {"item": "物流凭证", "purpose": "证明签收时间与快递状态", "how": "物流轨迹截图"},
            {"item": "商品实物照片/视频", "purpose": "证明质量问题或货不对板", "how": "拆包前、拆包后各拍一张"},
        ],
    },
    "ai": {
        "title": "AI / 数字产品纠纷",
        "icon": "🤖",
        "items": [
            {"item": "购买与订单记录", "purpose": "证明购买时间、价格、套餐内容", "how": "订单/收据/开通记录截图"},
            {"item": "服务承诺页面", "purpose": "证明宣传功效与实际不符", "how": "官网/宣传页/课程页截图存档"},
            {"item": "使用过程记录", "purpose": "证明服务未达承诺", "how": "对话记录、生成结果、报错截图"},
            {"item": "自动续费/扣款记录", "purpose": "证明未显著提醒或误扣", "how": "扣款短信与账单截图"},
            {"item": "客服交涉记录", "purpose": "证明商家拒绝处理", "how": "与客服的完整聊天/工单记录"},
        ],
    },
    "private": {
        "title": "私域 / 线下交易纠纷",
        "icon": "🏪",
        "items": [
            {"item": "付款凭证", "purpose": "证明交易与金额（转账/刷卡/现金收据）", "how": "转账记录、收据、小票截图"},
            {"item": "沟通记录", "purpose": "证明约定内容与商家承诺", "how": "微信/短信/电话录音中的关键承诺"},
            {"item": "商家主体信息", "purpose": "确定被投诉方（个人/店铺/公司）", "how": "营业执照、门头照、名片"},
            {"item": "商品/服务交付凭证", "purpose": "证明收到的东西与约定不符", "how": "实物照片、聊天确认记录"},
            {"item": "线下地址/时间线索", "purpose": "便于属地部门受理", "how": "交易时间、地点记录"},
        ],
    },
    "food": {
        "title": "食品安全纠纷",
        "icon": "🍽️",
        "items": [
            {"item": "剩余食品与外包装", "purpose": "关键物证（退一赔十的核心）", "how": "封存原样，勿丢弃"},
            {"item": "异物/变质照片视频", "purpose": "直观呈现问题", "how": "第一时间拍照录像"},
            {"item": "订单与小票", "purpose": "证明购买渠道与金额", "how": "外卖订单、小票截图"},
            {"item": "就医记录与票据", "purpose": "证明健康损害与损失", "how": "病历、发票、缴费记录"},
            {"item": "商家资质信息", "purpose": "核对经营许可，举报无证经营", "how": "平台商家页的证照截图"},
        ],
    },
    "service": {
        "title": "预付卡 / 服务纠纷",
        "icon": "🎫",
        "items": [
            {"item": "合同/协议/章程", "purpose": "证明退卡退款条款", "how": "电子合同或纸质合同拍照"},
            {"item": "充值/缴费记录", "purpose": "证明预付金额", "how": "转账、刷卡、收据截图"},
            {"item": "消费记录", "purpose": "证明剩余额度", "how": "消费明细、卡内余额截图"},
            {"item": "商家经营状态证据", "purpose": "证明跑路/闭店/服务缩水", "how": "门店照片、停业通知、官微公告"},
            {"item": "交涉记录", "purpose": "证明退费被拒", "how": "与商家/客服的沟通记录"},
        ],
    },
    "general": {
        "title": "通用证据清单",
        "icon": "📋",
        "items": [
            {"item": "订单/合同/收据", "purpose": "证明交易关系", "how": "截图或拍照保存"},
            {"item": "支付凭证", "purpose": "证明金额与时间", "how": "账单、转账记录"},
            {"item": "沟通记录", "purpose": "证明约定与交涉过程", "how": "聊天、邮件、工单、录音"},
            {"item": "商品/服务实物证据", "purpose": "证明问题本身", "how": "照片、视频、封存实物"},
            {"item": "商家主体信息", "purpose": "确定被投诉方", "how": "店铺名、营业执照、门头"},
            {"item": "损失凭证", "purpose": "证明实际损失", "how": "维修单、就医票据、误工证明"},
        ],
    },
}

DEFAULT_KEY = "general"

CATEGORY_TO_SCENARIO = {
    "网购纠纷": "online",
    "产品质量": "online",
    "虚假宣传": "ai",
    "食品安全": "food",
    "服务纠纷": "service",
    "价格欺诈": "online",
    "合同纠纷": "service",
    "其他": "general",
}


def get_evidence_checklist(scenario: str = "general") -> dict:
    key = scenario if scenario in SCENARIOS else DEFAULT_KEY
    data = SCENARIOS[key]
    return {
        "key": key,
        "title": data["title"],
        "icon": data["icon"],
        "items": data["items"],
    }


def get_evidence_checklist_by_category(category: str) -> dict:
    return get_evidence_checklist(CATEGORY_TO_SCENARIO.get(category, DEFAULT_KEY))


def list_scenarios() -> list:
    return [{"key": k, "title": v["title"], "icon": v["icon"]} for k, v in SCENARIOS.items()]
