#!/usr/bin/env python3
"""检索评测集格式校验 + 覆盖率统计。

用法：
    /opt/anaconda3/envs/rag_env/bin/python scripts/validate_eval_set.py
    /opt/anaconda3/envs/rag_env/bin/python scripts/validate_eval_set.py --file 其他/路径.jsonl

它做四件事：
1. 语法与字段校验（每行必须是合法 JSON，且含 query / expected_articles / category / source）
2. 法条 ID 校验（预期法条必须真实存在于法律知识库，防止写出不存在的条号）
3. 覆盖率统计（按 type / category / source 汇总，哪一类不足会提示）
4. 标注进度（还有多少条 expected_articles 是空的）

退出码：0 = 全部通过；1 = 存在错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from backend.services.law_seed import LAW_SEED  # noqa: E402

DEFAULT_FILE = os.path.join(REPO_ROOT, "docs", "资料", "检索评测", "eval_set.jsonl")

REQUIRED_FIELDS = ("query", "expected_articles", "category", "source")
VALID_SOURCES = ("真实", "改写", "构造")
VALID_TYPES = ("口语vs术语", "错别字简称", "已知缺陷", "多诉求混杂", "超范围")
MIN_CASES_PER_TYPE = 3  # 每类至少 3 条，避免某类只有一条、结论不可用


def build_valid_ids() -> set[str]:
    """知识库里真实存在的法条 ID 集合"""
    ids = set()
    for law_name, article, _content, _tags in LAW_SEED:
        ids.add(f"{law_name}-{article.replace('第', '').replace('条', '')}")
    return ids


def load(path: str) -> tuple[list[dict], list[str]]:
    cases: list[dict] = []
    errors: list[str] = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"第 {lineno} 行不是合法 JSON：{e.msg}")
                continue
            if not isinstance(item, dict):
                errors.append(f"第 {lineno} 行必须是 JSON 对象")
                continue
            item["__lineno"] = lineno
            cases.append(item)
    return cases, errors


def validate(cases: list[dict], valid_ids: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_queries: dict[str, int] = {}

    for item in cases:
        ln = item["__lineno"]
        for field in REQUIRED_FIELDS:
            if field not in item:
                errors.append(f"第 {ln} 行缺少字段 {field}")
        if not isinstance(item.get("query"), str) or not str(item.get("query", "")).strip():
            errors.append(f"第 {ln} 行 query 必须是非空字符串")
        expected = item.get("expected_articles")
        if not isinstance(expected, list):
            errors.append(f"第 {ln} 行 expected_articles 必须是数组")
            expected = []
        for article in expected:
            if not isinstance(article, str):
                errors.append(f"第 {ln} 行 expected_articles 只能放字符串")
            elif article not in valid_ids:
                errors.append(f"第 {ln} 行法条 ID 不存在于知识库：{article}")
        source = item.get("source")
        if source not in VALID_SOURCES:
            errors.append(f"第 {ln} 行 source 必须是 {'/'.join(VALID_SOURCES)} 之一，当前：{source!r}")
        case_type = item.get("type")
        if case_type is None:
            warnings.append(f"第 {ln} 行未填 type，无法统计五类覆盖情况")
        elif case_type not in VALID_TYPES:
            errors.append(f"第 {ln} 行 type 取值非法：{case_type!r}")
        if item.get("expect_abstain") is True and expected:
            errors.append(f"第 {ln} 行标记为应拒答，expected_articles 却非空")

        q = str(item.get("query", "")).strip()
        if q:
            if q in seen_queries:
                warnings.append(f"第 {ln} 行与第 {seen_queries[q]} 行 query 重复：{q[:24]}…")
            else:
                seen_queries[q] = ln

    return errors, warnings


def report(cases: list[dict]) -> None:
    total = len(cases)
    labeled = [
        c for c in cases
        if (isinstance(c.get("expected_articles"), list) and c["expected_articles"]) or c.get("expect_abstain") is True
    ]
    by_type = Counter(c.get("type", "（未填）") for c in cases)
    by_category = Counter(c.get("category", "（未填）") for c in cases)
    by_source = Counter(c.get("source", "（未填）") for c in cases)

    print(f"\n用例总数：{total}")
    print(f"已标注预期：{len(labeled)}   待标注：{total - len(labeled)}")

    print("\n按覆盖类型：")
    for t in VALID_TYPES:
        n = by_type.get(t, 0)
        flag = "✅" if n >= MIN_CASES_PER_TYPE else "⚠️ "
        print(f"  {flag} {t}：{n} 条")
    extra = {k: v for k, v in by_type.items() if k not in VALID_TYPES}
    for k, v in extra.items():
        print(f"  ⚠️  {k}：{v} 条（非标准分类）")

    print("\n按纠纷类别：")
    for k, v in by_category.most_common():
        print(f"  {k}：{v} 条")

    print("\n按来源：")
    for k in VALID_SOURCES:
        print(f"  {k}：{by_source.get(k, 0)} 条")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验检索评测集")
    parser.add_argument("--file", default=DEFAULT_FILE, help="评测集路径（默认 docs/资料/检索评测/eval_set.jsonl）")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"✗ 文件不存在：{args.file}", file=sys.stderr)
        return 1

    cases, errors = load(args.file)
    valid_ids = build_valid_ids()
    field_errors, warnings = validate(cases, valid_ids)
    errors.extend(field_errors)

    report(cases)

    if warnings:
        print("\n提醒：")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print("\n错误：")
        for e in errors:
            print(f"  ✗ {e}")
        print(f"\n校验未通过（{len(errors)} 个错误）")
        return 1

    print("\n✅ 校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
