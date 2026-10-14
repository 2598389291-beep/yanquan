#!/usr/bin/env python3
"""把法律知识库导出成人可读的索引（供人工撰写检索评测集时查阅）。

用法：
    /opt/anaconda3/envs/rag_env/bin/python scripts/gen_law_index.py

输出：docs/资料/检索评测/法条索引.md

为什么需要它：写评测集时必须能为每条 query 填写「预期命中的法条」，
而预期值要有一个稳定的 ID 口径，否则同一条法条会出现多种写法。
本脚本统一生成 `法律名称-条号` 形式的 ID（例如 食品安全法-148）。
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from backend.services.law_seed import LAW_SEED  # noqa: E402

OUTPUT = os.path.join(REPO_ROOT, "docs", "资料", "检索评测", "法条索引.md")


def article_id(law_name: str, article: str) -> str:
    """规范 ID：法律名称-条号数字（第148条 → 食品安全法-148）"""
    number = article.replace("第", "").replace("条", "")
    return f"{law_name}-{number}"


def main() -> int:
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for law_name, article, content, tags in LAW_SEED:
        grouped[law_name].append((article, content, tags))

    lines: list[str] = []
    lines.append("# 言权法律知识库索引（108 条 / 20 部法律）")
    lines.append("")
    lines.append("> 本文件由 `scripts/gen_law_index.py` 生成，请勿手工编辑。")
    lines.append("> 用途：撰写检索评测集时查阅，确定每条 query 的「预期命中法条」ID。")
    lines.append("")
    lines.append("## ID 口径")
    lines.append("")
    lines.append("`法律名称-条号数字`，例如：")
    lines.append("")
    lines.append("- `食品安全法-148`")
    lines.append("- `消费者权益保护法-55`")
    lines.append("- `网络交易监督管理办法-19`")
    lines.append("")
    lines.append("法条名称与条号一律以本索引为准（与 `backend/services/law_seed.py` 完全一致）。")
    lines.append("")

    total = 0
    for law_name in sorted(grouped, key=lambda k: (-len(grouped[k]), k)):
        items = grouped[law_name]
        lines.append(f"## {law_name}（{len(items)} 条）")
        lines.append("")
        lines.append("| ID | 标签（tags） | 条文内容 |")
        lines.append("|----|--------------|----------|")
        for article, content, tags in items:
            safe_content = content.replace("|", "｜")
            preview = safe_content if len(safe_content) <= 90 else safe_content[:90] + "…"
            lines.append(f"| `{article_id(law_name, article)}` | {tags} | {preview} |")
            total += 1
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"合计 {total} 条。")
    lines.append("")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"已生成：{OUTPUT}")
    print(f"共 {total} 条，来自 {len(grouped)} 部法律法规")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
