import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, PageBreak)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "参赛文档")
OUT_PDF = os.path.join(OUT_DIR, "小程序介绍文档.pdf")

NAVY = HexColor("#0F2B4C")
GOLD = HexColor("#B8923C")
GRAY = HexColor("#5B6B82")
LIGHT = HexColor("#F2F6FB")

FONT_NAME = "STSong-Light"
_FONT_CANDIDATES = [
    ("STHeiti", "/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("Songti", "/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    ("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf", None),
]
for name, path, idx in _FONT_CANDIDATES:
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        if idx is None:
            pdfmetrics.registerFont(TTFont(name, path))
        else:
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
        FONT_NAME = name
        break
    except Exception:
        continue
else:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
print("使用字体:", FONT_NAME)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_NAME, 9)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def header(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 22 * mm, A4[0], 22 * mm, stroke=0, fill=1)
    canvas.setFillColor(white)
    canvas.setFont(FONT_NAME, 12)
    canvas.drawString(20 * mm, A4[1] - 14 * mm, "言权宝权益助手（言权） · AI 消费者维权助手")
    canvas.setFillColor(HexColor("#D9BC78"))
    canvas.setFont(FONT_NAME, 9)
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 14 * mm, "2026 微信小程序开发者计划 · 参赛作品介绍")
    canvas.restoreState()


def build_styles():
    return {
        "title": ParagraphStyle("title", fontName=FONT_NAME, fontSize=22,
                                leading=30, alignment=TA_CENTER, textColor=NAVY, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", fontName=FONT_NAME, fontSize=13,
                                   leading=20, alignment=TA_CENTER, textColor=GOLD, spaceAfter=18),
        "h2": ParagraphStyle("h2", fontName=FONT_NAME, fontSize=15, leading=22,
                             textColor=NAVY, spaceBefore=18, spaceAfter=8),
        "body": ParagraphStyle("body", fontName=FONT_NAME, fontSize=11, leading=19,
                               textColor=HexColor("#222222"), alignment=TA_LEFT, spaceAfter=6),
        "bullet": ParagraphStyle("bullet", fontName=FONT_NAME, fontSize=11, leading=19,
                                 leftIndent=14, bulletIndent=2, spaceAfter=4),
        "small": ParagraphStyle("small", fontName=FONT_NAME, fontSize=9.5, leading=15,
                                textColor=GRAY),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    st = build_styles()
    doc = SimpleDocTemplate(OUT_PDF, pagesize=A4,
                            leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=32 * mm, bottomMargin=20 * mm,
                            title="言权宝权益助手（言权）· AI 消费者维权助手 - 参赛作品介绍",
                            author="言权团队")
    story = []

    story.append(Paragraph("言权宝权益助手 · AI 消费者维权助手", st["title"]))
    story.append(Paragraph("（简称「言权」）口述即出信，维权有依据 —— 2026 微信小程序开发者计划参赛作品", st["subtitle"]))

    # 一、作品简介
    story.append(Paragraph("一、小程序功能简介", st["h2"]))
    story.append(Paragraph(
        "「言权宝权益助手」（以下简称「言权」）是一款基于 AI 大模型的消费者维权小程序。用户只需口述或输入一段维权经历，"
        "系统即可自动生成一封结构完整、可直接提交的专业投诉信，并附带法律依据、维权路径、"
        "沟通话术和商家资质查验建议，全流程一站式解决“不知道怎么投诉、不会写投诉信”的痛点。", st["body"]))
    story.append(Paragraph("核心功能包括：", st["body"]))
    for item in [
        "语音维权：按住说话口述经历，支持最长 5 分钟长语音，自动转写为文字并把口语转为规范书面表达（支持嘈杂环境），把“写投诉信”的门槛从会写降到会说；",
        "文字输入与证据包：支持文字描述，可上传最多 6 张订单/聊天/物流截图，AI 自动识别订单号、金额、商家等关键信息；",
        "AI 投诉信生成：6 步生成管线（事实提取 → 法律检索 → 信函生成 → 资质建议 → 质检修复 → 话术生成），带分步进度反馈；",
        "法律溯源：内置 108 条高频消费维权条文（覆盖 20 部法律法规，涵盖网购、食品、服务、物流、虚假宣传、自动续费、预付卡、教育培训等场景）+ RAG 语义检索 + 场景标签精准匹配，每条法律依据附条文全文与官方检索链接，来源可追溯；",
        "即用模板库：内置 10 个高频纠纷通用投诉信模板（自动续费、快递丢件、预付卡退费、教育退费等），一键填入即可个性化生成；",
        "案例参考库：8 个脱敏维权案例展示同类问题的解决路径、周期与关键做法，帮助用户建立合理预期；",
        "官方入口一键复制：12315、黑猫投诉、国家邮政局、工信部申诉等官方渠道的搜索词与链接一键复制，解决“不知道找谁投诉”；",
        "维权路径指引：按纠纷类型推荐平台协商、12315 投诉/举报、法院起诉等渠道及分步指引；",
        "沟通话术模板：生成可直接复制发送给商家、平台、12315 的分步话术；",
        "记录与进度追踪：历史记录管理、状态流转（已生成→已复制→已提交→跟进中→已解决）；",
        "维权指南：内置 8 大常见纠纷场景的适用法律、行动步骤与沟通技巧；",
        "用户反馈闭环：结果页提供有用性评价与纠错入口，支撑生成质量持续迭代。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    # 二、应用场景
    story.append(Paragraph("二、应用场景", st["h2"]))
    for item in [
        "网购纠纷：买到假货、货不对板、商家拒绝退款或拉黑用户；",
        "食品安全：外卖吃出异物、食品变质过期，主张退一赔十；",
        "服务纠纷：健身房、美容院、培训机构预付卡跑路或拒绝退费；",
        "物流纠纷：快递丢件、破损、长时间延误（国家邮政局申诉通道）；",
        "数字消费：App 会员自动续费未提醒、运营商乱扣费（工信部申诉通道）；",
        "虚假宣传：直播间夸大功效、虚假促销、价格欺诈；",
        "售后推诿：商家或平台对合理售后诉求拖延、拒不处理。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    # 三、解决的实际问题
    story.append(Paragraph("三、解决的实际问题", st["h2"]))
    story.append(Paragraph(
        "据市场监管总局 2026 年 3 月发布的《2025 年消费者投诉举报呈现十大特点》，2025 年全国"
        "12315 平台及电话等渠道共受理消费者投诉、举报和咨询 4386.6 万件，其中投诉 2036.6 万件，"
        "首次突破 2000 万件、同比增长 9.3%，全年为消费者挽回经济损失 43.5 亿元。"
        "然而仍有大量消费者在权益受损后选择放弃维权，首要原因是"
        "“不会写投诉信、不知道怎么写”，其次是“不知道找谁投诉”。同时，12315 的"
        "“投诉”与“举报”是两个不同通道，多数用户容易混淆导致诉求被退回。", st["body"]))
    story.append(Paragraph(
        "「言权」解决的核心问题是：把普通人口语化的维权经历，转化为可直接提交的专业投诉文书，"
        "并告诉他该找谁、怎么提交、大概多久能解决。它与 12315、黑猫投诉等平台不是竞争关系，"
        "而是其上游的“投诉内容生产工具”——用户用言权生成投诉信与材料包后，再提交到 12315（求权威）"
        "或黑猫（求速度），形成“AI 生成 + 平台提交”的协作闭环。", st["body"]))

    # 四、技术开发方案
    story.append(Paragraph("四、技术开发方案", st["h2"]))
    story.append(Paragraph(
        "前端：微信小程序（Taro 4 + React + TypeScript + SCSS），采用自研深海蓝与鎏金设计系统，"
        "支持语音、文字、图片多模态输入，包含首页、生成、记录、详情、维权指南、我的、登录、引导、协议等 9 个页面；"
        "首页采用数据驱动设计，法条/模板/案例等知识库数据实时展示。", st["body"]))
    story.append(Paragraph(
        "后端：Python FastAPI 构建 RESTful API，SQLite 存储（WAL 模式 + 索引），Docker 容器化，"
        "部署于微信云托管；小程序端通过 wx.cloud.callContainer 云调用内网直连后端，"
        "无需配置服务器合法域名、无需公网流量，天然抗 DDoS，并支持微信用户态透传。", st["body"]))
    story.append(Paragraph(
        "AI 能力：阿里云百炼通义千问（qwen-plus 负责高质量文书生成，qwen-flash 负责事实提取、法律匹配与质检），"
        "DashScope 语音识别（paraformer）与图像识别（qwen-vl）；生成采用多步管线并行与快慢模型分工优化，"
        "经 10 类真实纠纷场景端到端压测，平均响应约 38 秒（P50 约 36 秒、P95 约 63 秒）；"
        "采用任务式分阶段生成，7-10 秒内先展示投诉信骨架，其余内容边生成边补全，前端轮询实时呈现进度，避免等待焦虑。", st["body"]))
    story.append(Paragraph(
        "双模式设计：未配置 API Key 时自动切换为纯规则演示管线（接口结构一致），保证项目开箱即可运行、可测试、可演示。", st["body"]))
    story.append(Paragraph(
        "工程化：68 个自动化测试覆盖 API、生成管线与数据库；知识库包含 108 条高频消费维权条文（覆盖 20 部法律法规）、"
        "10 个通用模板、8 个脱敏案例，均支持服务端热更新；用户数据按 token 隔离并做归属校验，"
        "配套用户协议与隐私政策。", st["body"]))

    # 五、创新点
    story.append(Paragraph("五、小程序创新点", st["h2"]))
    for item in [
        "口述即出信：以语音输入为核心交互，把“写投诉信”的门槛从“会写”降到“会说”，适配中老年等低数字化人群；",
        "法律依据可溯源：每条法条附全文与官方检索链接，形成“AI 生成 + 权威溯源”的双重信任背书；",
        "多步 AI 管线 + 自我质检：事实提取、法律匹配、信函生成、质检修复、话术生成全链路闭环，缺失信息以占位符标注，杜绝编造；",
        "即用模板 + 案例参考：10 个高频模板一键填入生成、8 个脱敏案例展示解决路径与周期，把“维权经验”产品化；",
        "官方入口一键复制：将分散在多个部门的投诉渠道聚合为可复制的入口指引，降低“不知道找谁”的行动门槛；",
        "证据包管理：多张截图批量识别并随投诉信保存，一键复制“投诉信 + 证据清单 + 提交指引”完整材料包；",
        "双模式降级设计：无外部服务也可完整运行，演示与联调零门槛；",
        "反馈闭环：用户评价与纠错数据回流，为生成质量持续迭代提供依据。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    # 六、上线情况与用户反馈
    story.append(Paragraph("六、上线情况与用户反馈", st["h2"]))
    story.append(Paragraph(
        "作品已完成开发并正式上线，当前可在微信内正常访问使用，核心链路（语音输入 → 事实提取 → 法律检索 → "
        "投诉信生成 → 法条溯源 → 材料包复制）运行稳定。", st["body"]))
    story.append(Paragraph(
        "上线后已获得首批真实用户使用，覆盖网购、快递、预付卡退费等典型纠纷场景，用户完成端到端全流程体验，"
        "并回收了生成质量评价与纠错反馈，验证了产品在真实场景下的可用性；相关反馈已回流用于生成管线与提示词的迭代优化。", st["body"]))
    story.append(Paragraph(
        "下一步计划：持续积累真实用户反馈并扩大种子用户规模，完善投诉进度的订阅消息提醒；"
        "接入微信 AI 生态，使小程序能力可被微信 AI 识别与调用，进一步降低用户获取门槛；"
        "评估将法条溯源由官方检索链接升级为权威法律数据库 API 原文。", st["body"]))

    # 七、团队情况
    story.append(Paragraph("七、团队情况", st["h2"]))
    story.append(Paragraph(
        "本小程序「言权宝权益助手」（简称「言权」）由个人独立开发完成（个人参赛，无其他团队成员）。"
        "开发者系计算机科学与技术专业大二在读学生，独立完成市场与竞品调研、产品定位与原型设计、"
        "前端小程序开发（Taro + React + TypeScript）、后端服务开发（FastAPI + SQLite）、"
        "AI 生成管线与提示词工程、法律知识库建设、自动化测试（68 个用例）及云端部署上线全流程，"
        "具备从 0 到 1 独立构建并交付完整产品的工程能力。", st["body"]))

    # 八、引用说明
    story.append(Paragraph("八、引用第三方成果说明", st["h2"]))
    story.append(Paragraph(
        "本作品开发过程中使用了以下第三方开源框架与平台服务，在此如实说明：", st["body"]))
    for item in [
        "开源框架：Taro（京东开源跨端框架）、React、FastAPI、SQLite、DashScope Python SDK；",
        "AI 平台服务：阿里云百炼（通义千问大模型）、DashScope 语音识别与图像识别 API；",
        "部署平台：微信云托管（腾讯云，wx.cloud.callContainer 云调用）；",
        "数据来源：国家市场监督管理总局《2025 年消费者投诉举报呈现十大特点》（2026 年 3 月发布，www.samr.gov.cn）、国家法律法规数据库（flk.npc.gov.cn）官方检索链接；",
        "除上述第三方成果外，产品设计、提示词工程、生成管线、知识库内容、前后端代码与文档均为团队原创。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.8, color=GOLD))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "注：本作品定位为投诉文书辅助生成工具，生成内容仅供参考，不构成法律意见；提交前请用户核对事实与法律依据。", st["small"]))

    def decorate(canvas, doc):
        header(canvas, doc)
        footer(canvas, doc)

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print("已生成:", OUT_PDF)


if __name__ == "__main__":
    main()
