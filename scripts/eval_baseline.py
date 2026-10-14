#!/usr/bin/env python3
"""用评测集测量「当前检索」的能力，产出基线报告。

用法：
    /opt/anaconda3/envs/rag_env/bin/python scripts/eval_baseline.py
    /opt/anaconda3/envs/rag_env/bin/python scripts/eval_baseline.py --topk 10

指标定义（先看这段再改代码）：
- recall@k：该条用例的预期法条中，有多少比例出现在前 k 个候选里。
  例：预期 2 条，前 10 里只找到 1 条 → recall@10 = 0.5。
- hit@k：预期法条里只要有一条进了前 k，就算命中（0/1）。它衡量"能不能找到"。
- all_hit@k：预期法条全部进了前 k 才算命中（0/1）。它衡量"找得全不全"。
- MRR：第一条命中的排名取倒数再对全部用例求平均（第 1 位=1.0，第 3 位=0.33）。
  它衡量"命中的法条排得够不够靠前"。
- 拒答：标了 expect_abstain 的用例，正确行为是不检索出任何法条。
  本脚本不做判定，只统计这些用例的最高分，用来观察"拒答线该划在哪"。

注意：本脚本测的是**召回层**（n-gram + 标签加权），不含 LLM 精排。
原因：精排要花真钱、且结果不稳定；召回层的 Recall 才是可以直接对比改进效果的指标。
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from backend.services.law_seed import LAW_SEED  # noqa: E402
from backend.services.retrieval import retrieve_laws  # noqa: E402

DEFAULT_EVAL = os.path.join(REPO_ROOT, "docs", "资料", "检索评测", "eval_set.jsonl")
DEFAULT_REPORT = os.path.join(REPO_ROOT, "docs", "资料", "检索评测", "基线报告.md")


def article_id(law_name: str, article: str) -> str:
    return f"{law_name}-{article.replace('第', '').replace('条', '')}"


def load_cases(path: str) -> list[dict]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def recall_at_k(returned: list[str], expected: list[str], k: int) -> float:
    """预期法条中出现在前 k 的比例。expected 为空时返回 0（拒答用例单独统计）。"""
    if not expected:
        return 0.0
    top = set(returned[:k])
    return sum(1 for e in expected if e in top) / len(expected)


def hit_at_k(returned: list[str], expected: list[str], k: int) -> int:
    """预期法条里只要有一条进了前 k 就是 1。"""
    if not expected:
        return 0
    return 1 if any(e in set(returned[:k]) for e in expected) else 0


def all_hit_at_k(returned: list[str], expected: list[str], k: int) -> int:
    """预期法条全部进了前 k 才是 1。"""
    if not expected:
        return 0
    return 1 if all(e in set(returned[:k]) for e in expected) else 0


def reciprocal_rank(returned: list[str], expected: list[str]) -> float:
    """第一条命中的排名的倒数（没命中记 0）。"""
    if not expected:
        return 0.0
    for idx, item in enumerate(returned, 1):
        if item in expected:
            return 1.0 / idx
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="检索基线评测")
    parser.add_argument("--file", default=DEFAULT_EVAL)
    parser.add_argument("--out", default=DEFAULT_REPORT)
    parser.add_argument("--topk", type=int, default=10, help="召回条数（默认 10，与线上一致）")
    args = parser.parse_args()

    cases = load_cases(args.file)
    # 确保知识库已初始化（脚本可能先于服务运行）
    from backend.database import init_db
    init_db()
    kb = {article_id(l, a): c for l, a, c, _t in LAW_SEED}

    scored: list[dict] = []
    abstain_scores: list[float] = []

    for case in cases:
        query = case["query"]
        expected = case.get("expected_articles") or []
        hits = retrieve_laws(query, k=args.topk)
        returned_ids = [article_id(h["law_name"], h["article"]) for h in hits]
        top1_score = hits[0]["_score"] if hits else 0.0

        if case.get("expect_abstain"):
            abstain_scores.append(top1_score)
            scored.append({
                "query": query, "type": case.get("type"), "category": case.get("category"),
                "expected": [], "returned": returned_ids, "top1_score": top1_score,
                "abstain": True, "recall5": None, "recall10": None,
                "hit1": None, "hit3": None, "all10": None, "mrr": None,
                "missing": [],
            })
            continue

        top = set(returned_ids)
        missing = [e for e in expected if e not in top]
        scored.append({
            "query": query, "type": case.get("type"), "category": case.get("category"),
            "expected": expected, "returned": returned_ids, "top1_score": top1_score,
            "abstain": False,
            "recall5": recall_at_k(returned_ids, expected, 5),
            "recall10": recall_at_k(returned_ids, expected, args.topk),
            "hit1": hit_at_k(returned_ids, expected, 1),
            "hit3": hit_at_k(returned_ids, expected, 3),
            "all10": all_hit_at_k(returned_ids, expected, args.topk),
            "mrr": reciprocal_rank(returned_ids, expected),
            "missing": missing,
        })

    real = [s for s in scored if not s["abstain"]]
    overall = {
        "n": len(real),
        "recall5": statistics.fmean(s["recall5"] for s in real) if real else 0.0,
        "recall10": statistics.fmean(s["recall10"] for s in real) if real else 0.0,
        "hit1": statistics.fmean(s["hit1"] for s in real) if real else 0.0,
        "hit3": statistics.fmean(s["hit3"] for s in real) if real else 0.0,
        "all10": statistics.fmean(s["all10"] for s in real) if real else 0.0,
        "mrr": statistics.fmean(s["mrr"] for s in real) if real else 0.0,
    }

    by_type: dict[str, list[dict]] = defaultdict(list)
    for s in real:
        by_type[s["type"] or "（未填）"].append(s)

    failures = [s for s in real if s["recall10"] < 1.0]

    # ---------- 报告 ----------
    lines: list[str] = []
    lines.append("# 言权检索基线报告")
    lines.append("")
    lines.append(f"- 评测集：`{os.path.relpath(args.file, REPO_ROOT)}`（{len(cases)} 条用例，其中拒答 {len(abstain_scores)} 条）")
    lines.append(f"- 被测对象：`backend/services/retrieval.py` 的 `retrieve_laws()`（字符 2/3-gram 余弦 + 标签加权 0.25），不含 LLM 精排")
    lines.append(f"- 召回条数：top-{args.topk}")
    lines.append("")
    lines.append("## 一、总体指标")
    lines.append("")
    lines.append("| 指标 | 数值 | 含义 |")
    lines.append("|------|------|------|")
    lines.append(f"| Recall@5 | {overall['recall5']:.3f} | 预期法条进前 5 的比例 |")
    lines.append(f"| **Recall@{args.topk}** | **{overall['recall10']:.3f}** | 预期法条进前 {args.topk} 的比例（主指标） |")
    lines.append(f"| Hit@1 | {overall['hit1']:.3f} | 第一名就命中至少一条的用例占比 |")
    lines.append(f"| Hit@3 | {overall['hit3']:.3f} | 前 3 命中至少一条的用例占比 |")
    lines.append(f"| All-Hit@{args.topk} | {overall['all10']:.3f} | 预期法条**全部**进前 {args.topk} 的用例占比 |")
    lines.append(f"| MRR | {overall['mrr']:.3f} | 命中位置的倒数均值（越接近 1 越靠前） |")
    lines.append("")
    lines.append("## 二、按覆盖类型")
    lines.append("")
    lines.append("| 类型 | 用例数 | Recall@10 | Hit@3 | MRR |")
    lines.append("|------|--------|-----------|-------|-----|")
    for t, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        lines.append(
            f"| {t} | {len(items)} | "
            f"{statistics.fmean(i['recall10'] for i in items):.3f} | "
            f"{statistics.fmean(i['hit3'] for i in items):.3f} | "
            f"{statistics.fmean(i['mrr'] for i in items):.3f} |"
        )
    lines.append("")
    lines.append("## 三、失败用例（预期法条未全部召回）")
    lines.append("")
    if not failures:
        lines.append("全部用例的预期法条都进了候选。")
    else:
        lines.append(f"共 {len(failures)} / {len(real)} 条未完全召回：")
        lines.append("")
        lines.append("| # | query | 预期 | 漏掉的 | 实际召回的（前 5） |")
        lines.append("|---|-------|------|--------|---------------------|")
        for i, s in enumerate(failures, 1):
            expected_txt = "、".join(s["expected"])
            missing_txt = "、".join(s["missing"])
            got = "、".join(s["returned"][:5])
            lines.append(f"| {i} | {s['query']} | {expected_txt} | **{missing_txt}** | {got} |")
        lines.append("")
        miss_counter = Counter(m for s in failures for m in s["missing"])
        lines.append("被漏掉最多的法条：")
        lines.append("")
        for article, n in miss_counter.most_common(10):
            lines.append(f"- `{article}`：漏 {n} 次")
    lines.append("")
    lines.append("## 四、拒答线的观察")
    lines.append("")
    if abstain_scores:
        non_abstain = [s["top1_score"] for s in real]
        lines.append(f"- 拒答用例最高分：{sorted(round(x, 4) for x in abstain_scores)}")
        if non_abstain:
            lines.append(f"- 非拒答用例最高分：最小 {min(non_abstain):.4f}，中位 {statistics.median(non_abstain):.4f}，最大 {max(non_abstain):.4f}")
            overlap = [x for x in abstain_scores if x >= min(non_abstain)]
            if overlap:
                lines.append(f"- ⚠️ 两类分数有重叠（{len(overlap)} 条拒答用例的分数不低于非拒答用例的最低分），单靠分数阈值无法完全区分，需要额外的范围判断")
            else:
                lines.append("- 两类分数目前是可分的，可以据此设一个拒答阈值（但仍建议加规则判断）")
    lines.append("")
    lines.append("## 五、这份基线怎么用")
    lines.append("")
    lines.append("- 后续任何改动（口语词典扩展、向量召回、RRF 融合）都用**同一份评测集**复测，对比 Recall@10 / MRR / 失败用例数")
    lines.append("- 失败用例列表就是改进清单：优先解决被漏掉次数最多的那几条法条")
    lines.append("- 面试可讲的完整链条：先建评测集 → 量出基线 → 定位失败原因 → 改进 → 复测对比")
    lines.append("")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"评测用例：{len(real)} 条（另 {len(abstain_scores)} 条拒答）")
    print(f"Recall@5={overall['recall5']:.3f}  Recall@{args.topk}={overall['recall10']:.3f}  "
          f"Hit@1={overall['hit1']:.3f}  Hit@3={overall['hit3']:.3f}  MRR={overall['mrr']:.3f}")
    print(f"未完全召回：{len(failures)} / {len(real)} 条")
    print(f"报告已写入：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
