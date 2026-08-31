#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「言权」小程序技术架构概览 PDF（面向资深程序员的技术沟通文档）

用法：python3 scripts/generate_arch_overview.py
输出：~/Desktop/言权小程序技术架构概览.pdf
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

FONT_NAME = "STSong-Light"
for name, path, idx in [
    ("STHeiti", "/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("Songti", "/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    ("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf", None),
]:
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx) if idx is not None else TTFont(name, path))
        FONT_NAME = name
        break
    except Exception:
        continue
else:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

NAVY = HexColor("#0F2B4C")
GOLD = HexColor("#B8923C")
GRAY = HexColor("#5B6B82")
LIGHT = HexColor("#F2F6FB")


def styles():
    return {
        "title": ParagraphStyle("t", fontName=FONT_NAME, fontSize=22, leading=30, alignment=TA_CENTER, textColor=NAVY, spaceAfter=4),
        "subtitle": ParagraphStyle("s", fontName=FONT_NAME, fontSize=12, leading=18, alignment=TA_CENTER, textColor=GRAY, spaceAfter=16),
        "h2": ParagraphStyle("h2", fontName=FONT_NAME, fontSize=15, leading=22, textColor=NAVY, spaceBefore=16, spaceAfter=8),
        "body": ParagraphStyle("b", fontName=FONT_NAME, fontSize=10.5, leading=18, textColor=HexColor("#222222"), spaceAfter=5),
        "bullet": ParagraphStyle("bl", fontName=FONT_NAME, fontSize=10.5, leading=18, leftIndent=14, bulletIndent=2, spaceAfter=3),
        "small": ParagraphStyle("sm", fontName=FONT_NAME, fontSize=9, leading=14, textColor=GRAY),
    }


def arch_diagram():
    """系统架构图（reportlab 图形绘制）"""
    d = Drawing(440, 250)
    box_w, box_h = 120, 46
    colors = {"client": HexColor("#E7EFFB"), "gw": HexColor("#F7F0DF"), "back": HexColor("#EAF4EC"), "ai": HexColor("#F3E8F7")}

    def box(x, y, w, h, text, fill, font=10.5):
        d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=NAVY, strokeWidth=0.8))
        d.add(String(x + w / 2, y + h / 2, text, fontName=FONT_NAME, fontSize=font, fillColor=NAVY, textAnchor="middle"))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=GOLD, strokeWidth=1.2))
        d.add(Polygon([x2, y2, x2 - 5, y2 - 3, x2 - 5, y2 + 3], fillColor=GOLD, strokeColor=GOLD))

    # 客户端
    box(20, 200, 150, 40, "微信小程序（Taro 4 + React + TS）\n首页/生成/记录/我的/指南", colors["client"], 9)
    box(20, 150, 150, 40, "语音 / 文字 / 截图输入\n结果展示 · 复制 · 分享", colors["client"], 9)
    # 云调用
    box(240, 175, 170, 40, "wx.cloud.callContainer\n云调用（内网链路，免域名备案）", colors["gw"], 9)
    arrow(170, 220, 240, 200)
    arrow(170, 170, 240, 195)
    # 后端
    box(20, 60, 200, 70, "后端服务（Python FastAPI · Docker · 微信云托管）\n路由层：complaint / evidence / guide / laws / feedback\n服务层：任务管理器 · 生成管线 · RAG · ASR · OCR\n数据层：SQLite（users/complaints/legal_knowledge/feedback/usage）", colors["back"], 8.5)
    arrow(240, 195, 220, 100)
    # 外部 AI
    box(290, 20, 130, 110, "外部 AI 服务\n阿里云百炼\nqwen-plus（信函/质检）\nqwen-flash（事实/匹配/话术）\nDashScope\nparaformer（ASR）\nqwen-vl（OCR）", colors["ai"], 8.5)
    arrow(220, 90, 290, 75)
    # 云存储
    box(20, 0, 150, 40, "对象存储（云存储）\n语音/证据文件中转（绕开 100KB 限制）", colors["gw"], 8.5)
    arrow(95, 150, 60, 42)
    return d


def main():
    out = os.path.join(os.path.expanduser("~"), "Desktop", "言权小程序技术架构概览.pdf")
    st = styles()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=24 * mm, bottomMargin=18 * mm,
                            title="言权小程序 · 技术架构概览", author="言权开发者")
    story = []
    story.append(Paragraph("言权宝权益助手（言权）", st["title"]))
    story.append(Paragraph("AI 消费者维权小程序 · 技术架构概览（面向技术评审）", st["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD))

    # 一、项目定位
    story.append(Paragraph("一、项目定位", st["h2"]))
    story.append(Paragraph(
        "言权是一款 AI 消费者维权小程序：用户通过语音、文字或订单截图描述维权经历，系统自动生成可直接提交的专业投诉信，"
        "并附带可溯源的法律依据、维权路径、沟通话术与官方渠道入口。产品定位是 12315 / 黑猫等投诉平台的\u201c上游文书生产工具\u201d，"
        "2026 微信小程序开发者计划参赛作品，已上线（个人主体）。", st["body"]))

    # 二、总体架构
    story.append(Paragraph("二、总体架构", st["h2"]))
    story.append(arch_diagram())
    story.append(Spacer(1, 4))
    for item in [
        "小程序端：9 个页面（首页/生成/记录/我的/详情/指南/登录/协议/引导），Taro 4 + React + TypeScript + SCSS，自研深海蓝鎏金设计系统；",
        "通信：wx.cloud.callContainer 云调用内网链路，不依赖合法域名、不产生公网流量；",
        "后端：Python FastAPI + SQLite，Docker 容器化部署于微信云托管，环境变量注入密钥；",
        "AI：阿里云百炼通义千问（qwen-plus / qwen-flash）+ DashScope 语音识别（paraformer）与图像识别（qwen-vl）；",
        "存储：音频/证据经云存储中转（规避云调用 100KB 请求体上限）。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    # 三、技术栈
    story.append(Paragraph("三、技术栈明细", st["h2"]))
    rows = [
        ["层", "技术", "说明"],
        ["前端", "Taro 4 / React / TS / SCSS", "一套代码编译到微信小程序；H5 预览模式用于开发"],
        ["后端", "Python 3.11 / FastAPI", "RESTful API；异步 + 线程池跑同步 AI 调用"],
        ["数据", "SQLite（WAL）", "5 张表；JSON 字段存储结构化业务数据"],
        ["AI", "qwen-plus / qwen-flash", "快慢模型分工：flash 做事实/匹配/话术，plus 做信函/质检"],
        ["语音", "DashScope paraformer", "mp3 直转写；支持最长 5 分钟长语音"],
        ["OCR", "DashScope qwen-vl", "订单/聊天截图关键信息提取"],
        ["部署", "微信云托管 + Docker", "云调用内网接入；环境变量注入密钥"],
        ["测试", "pytest", "64 个自动化测试覆盖 API/管线/数据库/配额"],
    ]
    t = Table(rows, colWidths=[24 * mm, 55 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FONT_NAME), ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D5DCE7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    # 四、核心生成管线
    story.append(Paragraph("四、核心生成管线（任务式分阶段）", st["h2"]))
    story.append(Paragraph(
        "为解决\u201c等 50 秒白屏\u201d的体验问题，生成改为异步任务 + 前端轮询：后端任务管理器逐步推进，"
        "投诉信骨架（6 大板块）约 7-10 秒先返回，完整文书约 30 秒补齐。", st["body"]))
    for item in [
        "Step 1 事实提取（flash）：口语 → 结构化关键信息（平台/商品/金额/时间/诉求/缺失字段）；",
        "Step 2 法律匹配（flash + RAG）：从 108 条知识库中召回候选，LLM 精排 1-3 条，再经知识库白名单校验（防幻觉）；",
        "Step 3 骨架生成（flash）：六板块投诉信骨架先行返回；",
        "Step 4 完整文书（plus）与话术（flash）并行生成；",
        "Step 5 质检修复（flash）：金额/法条/诉求/格式自动审查并修复；",
        "Step 6 组装：资质建议（规则）、渠道建议、法律溯源链接；",
        "降级策略：每一步失败均回退到纯规则实现（demo.py），保证任何情况都有结果；未配置 API Key 时整体走演示模式。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    # 五、RAG 与法律溯源
    story.append(Paragraph("五、法律知识库与 RAG", st["h2"]))
    story.append(Paragraph(
        "知识库内置 108 条高频消费维权条文（覆盖 20 部法律法规），每条含适用场景标签。检索链路：标签/文本召回 → LLM 精排 → "
        "白名单校验（只允许知识库内真实条文）→ 原文覆盖 + 国家法律法规数据库官方检索链接，杜绝编造。"
        "同步提供 10 个通用投诉模板、8 个脱敏案例，均服务端热更新。", st["body"]))

    # 六、数据库（字段级明细）
    story.append(Paragraph("六、数据库设计（SQLite 5 表 · 字段级）", st["h2"]))
    story.append(Paragraph("存储：SQLite 单文件（WAL 模式）。业务表 user_id 用 TEXT：游客=设备号 dev_xxx，登录后=账号 ID，因此不设外键。JSON 字段（法条/路径/订单/证据/标签）以 TEXT 存储。", st["body"]))

    def field_table(title, header, rows, note=None):
        story.append(Paragraph(title, st["h2"]))
        t = Table([header] + rows, colWidths=[38 * mm, 32 * mm, 99 * mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#D5DCE7")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        if note:
            story.append(Paragraph(note, st["small"]))

    field_table(
        "6.1 users · 用户账号（邮箱 / 微信双登录）",
        ["字段", "类型", "说明"],
        [
            ["id", "INTEGER PK", "账号 ID（登录后 user_id 引用）"],
            ["email", "TEXT UNIQUE", "邮箱（邮箱密码登录，首次登录自动注册）"],
            ["password_hash", "TEXT", "密码哈希（PBKDF2-SHA256 + 随机盐，不存明文）"],
            ["openid", "TEXT UNIQUE", "微信 openid（微信登录）"],
            ["phone", "TEXT", "手机号（兼容旧数据，可空）"],
            ["nickname / avatar", "TEXT", "昵称 / 头像"],
            ["token", "TEXT", "登录令牌"],
            ["token_expires_at", "TIMESTAMP", "令牌过期时间"],
            ["created_at", "TIMESTAMP", "注册时间"],
        ],
    )

    field_table(
        "6.2 legal_knowledge · 法律知识库（问题/条文库，RAG 检索源）",
        ["字段", "类型", "说明"],
        [
            ["id", "INTEGER PK", "主键"],
            ["law_name", "TEXT", "法律名称（消费者权益保护法等）"],
            ["article", "TEXT", "条文编号（第55条）"],
            ["content", "TEXT", "条文内容（原文/权威摘要）"],
            ["tags", "TEXT(JSON)", "适用场景标签，如 [\"欺诈\",\"退一赔三\",\"假货\"]"],
            ["created_at", "TIMESTAMP", "入库时间"],
        ],
        "注：启动时从 law_seed.py 幂等灌入 108 条/20 部法律；检索按 tags+文本召回 → LLM 精排 → 白名单校验。",
    )

    field_table(
        "6.3 complaints · 投诉记录（核心业务表）",
        ["字段", "类型", "说明"],
        [
            ["id", "INTEGER PK", "投诉单 ID"],
            ["user_id", "TEXT", "归属者（设备号 / 账号 ID）"],
            ["raw_text", "TEXT", "用户原始描述"],
            ["complaint_letter", "TEXT", "生成的投诉信全文"],
            ["legal_basis", "TEXT(JSON)", "引用法条列表"],
            ["action_path", "TEXT(JSON)", "维权路径步骤"],
            ["category", "TEXT", "纠纷分类"],
            ["order_info", "TEXT(JSON)", "订单信息（平台/商家/金额/订单号）"],
            ["status", "TEXT", "状态（默认 generated）"],
            ["evidence", "TEXT(JSON)", "证据列表（文件名/链接）"],
            ["created_at", "TIMESTAMP", "创建时间"],
        ],
        "索引：idx_complaints_user_created (user_id, created_at DESC)，支撑按用户倒序拉取最近记录。",
    )

    field_table(
        "6.4 feedback · 用户反馈",
        ["字段", "类型", "说明"],
        [
            ["id", "INTEGER PK", "主键"],
            ["complaint_id", "INTEGER", "关联投诉单"],
            ["user_id", "TEXT", "反馈者"],
            ["rating", "TEXT", "helpful / unhelpful"],
            ["comment", "TEXT", "具体意见"],
            ["created_at", "TIMESTAMP", "反馈时间"],
        ],
    )

    field_table(
        "6.5 usage_stats · 免费额度统计",
        ["字段", "类型", "说明"],
        [
            ["user_id", "TEXT PK", "用户（每用户一行）"],
            ["used_count", "INTEGER", "已用次数"],
            ["updated_at", "TIMESTAMP", "最近更新时间"],
        ],
        "额度逻辑：每用户默认 10 次，仅成功生成才计数；管理员白名单账号（ADMIN_USER_ID + 登录态）不限次。",
    )

    # 七、云调用与部署
    story.append(Paragraph("七、云调用与部署", st["h2"]))
    for item in [
        "wx.cloud.callContainer 内网直连云托管：免配置合法域名、免公网流量、天然抗 DDoS；",
        "云调用请求体 100KB 上限：音频/图片先传云存储，仅传临时链接/fileID 给后端；",
        "环境变量注入：DASHSCOPE_API_KEY、ADMIN_USER_ID（管理员免额度白名单）、DATABASE_URL；",
        "幂等建表 + 老库迁移，重复部署不破坏数据。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    # 八、工程化与质量
    story.append(Paragraph("八、工程化与质量", st["h2"]))
    for item in [
        "64 个自动化测试：API 集成、6 大场景管线、额度配额、管理员权限边界、防幻觉校验；",
        "双模式：演示模式（无 Key 秒出，接口结构一致）与 LLM 模式自动切换；",
        "防编造：缺失信息强制【请补充】占位，代码级净化（金额/日期/订单号/企业名）；",
        "免费额度：每设备/账号 10 次，管理员白名单仅限本人账号（需登录）无限次；",
        "合规：用户协议/隐私政策内置、ICP 备案通过、AI 生成内容已如实声明。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    # 九、限制与路线
    story.append(Paragraph("九、已知限制与演进路线", st["h2"]))
    for item in [
        "SQLite 单文件未挂盘，容器重启数据清零 → 迁移云数据库（MySQL/文档型）；",
        "证据上传仍走 base64，正式环境需迁移云存储（语音已迁移）；",
        "微信登录需在云端配置 WECHAT_APPID/SECRET；支付能力需企业主体；",
        "后续：知识库半自动进化（公开案例结构化入库 + 人工审核）、案例/模板持续扩充。",
    ]:
        story.append(Paragraph(item, st["bullet"], bulletText="•"))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.8, color=GOLD))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "说明：本概览为开发者本人整理的参赛作品技术文档；AI 平台、开源框架均为第三方成果，已在参赛介绍文档中如实声明。", st["small"]))

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 20 * mm, A4[0], 20 * mm, stroke=0, fill=1)
        canvas.setFillColor(white)
        canvas.setFont(FONT_NAME, 11)
        canvas.drawString(20 * mm, A4[1] - 13 * mm, "言权 · AI 消费者维权小程序")
        canvas.setFillColor(HexColor("#D9BC78"))
        canvas.setFont(FONT_NAME, 9)
        canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 13 * mm, "技术架构概览")
        canvas.setFont(FONT_NAME, 9)
        canvas.setFillColor(GRAY)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print("已生成:", out)


if __name__ == "__main__":
    main()
