#!/usr/bin/env python3
"""言权后端批量压测脚本

用途：对本地启动的后端（backend/run.sh）做批量调用压测，统计成功率、响应时间
（平均值 / P95 / P99）和失败原因分布，并把结果写成 markdown 报告。

用法（务必使用 rag_env，避免污染 base 环境）：

    # 1) 另开一个终端启动后端
    bash backend/run.sh

    # 2) 跑压测（默认 10 个场景 × 每个 100 次 = 1000 次请求）
    /opt/anaconda3/envs/rag_env/bin/python scripts/benchmark.py

    # 先小样本验证脚本本身（推荐第一次这么跑）
    /opt/anaconda3/envs/rag_env/bin/python scripts/benchmark.py --repeat 2 --concurrency 2

    # 后端配了真实 API Key（LLM 模式）时，超过 50 次请求需要显式确认成本
    /opt/anaconda3/envs/rag_env/bin/python scripts/benchmark.py --allow-cost

设计说明：
- 每个场景内部「连续调用」N 次（默认 100 次），场景之间最多并发 --concurrency 个；
- 每次请求使用独立的合成 user_id，避免命中后端「每用户 10 次免费额度」而全部失败
  （这是压测的刻意设计，不是绕过鉴权：真实用户额度逻辑由 test_api.py 覆盖）；
- 不依赖第三方库，只用标准库，避免额外安装污染环境。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import threading
import time
import urllib.error
import platform
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "docs", "benchmark.md")

# ============================================================
# 10 个真实维权场景
# ============================================================

SCENARIOS: list[tuple[str, str]] = [
    (
        "fake_goods",
        "上个月在拼多多一家店铺买了双运动鞋，花了 399 元，收到货发现是假货，"
        "鞋标和正品完全不一样，找商家沟通一直说是我自己看错了，不同意退款，"
        "我要求退款并且退一赔三。",
    ),
    (
        "expired_food",
        "前天在美团外卖点了一份炸鸡，吃到一半发现里面有一根头发，当天晚上肚子疼去医院看了急诊，"
        "医药费花了 380 元，找商家说只愿意退这份外卖的钱 38 元，我要求赔偿医药费并按食品安全法赔偿。",
    ),
    (
        "express_lost",
        "我寄了一个快递，里面是价值 1200 元的化妆品，快递显示已签收但我根本没收到，"
        "联系快递公司客服推了半个月，只肯按运费的三倍赔我 36 元，我要求按实际价值赔偿。",
    ),
    (
        "prepaid_card",
        "去年在小区楼下的健身房办了一张年卡，花了 3800 元，今年 3 月去的时候发现门店已经关门了，"
        "老板电话打不通微信也不回，还有很多会员跟我一样，我要求退还剩余费用。",
    ),
    (
        "false_ad",
        "在网上看到一个英语培训课程宣传说“保过、不过全额退款”，我交了 6800 元，"
        "结果没通过考试去找他们退费，对方说合同里写了不退款，我要求按照宣传承诺全额退款。",
    ),
    (
        "phone_quality",
        "在京东买的一部手机 4299 元，用了不到两个月就自动关机开不了机，"
        "售后检测说是主板问题但不肯换新只肯维修，我要求换新或者退货退款。",
    ),
    (
        "training_refund",
        "给孩子报了一个线下美术培训班，交了 9600 元一学期的费用，才上了三次课，"
        "机构突然通知停课说要搬迁，拖了两个月还没复课，我要求退还剩下的学费 8000 元。",
    ),
    (
        "telecom_charge",
        "我的手机号在没有任何通知的情况下被开通了每个月 30 元的增值业务，"
        "已经扣了 8 个月一共 240 元，打客服电话说是我自己订购的，我要求退还被扣的费用。",
    ),
    (
        "takeaway_hygiene",
        "在饿了么点了一份麻辣烫 45 元，吃到后面发现汤里有只小虫子，"
        "拍照发给商家，对方说不是他们的问题拒绝处理，我要求赔偿并希望平台查处。",
    ),
    (
        "live_shopping",
        "在抖音直播间买了一套护肤品，主播说是专柜正品 899 元，收到后发现包装和批号都对不上，"
        "去专柜验证说不是他们家的货，申请退款被商家拒绝，我要求退款并退一赔三。",
    ),
]


# ============================================================
# HTTP 工具（标准库实现）
# ============================================================


def http_json(
    method: str,
    url: str,
    payload: Optional[dict] = None,
    timeout: float = 120.0,
) -> tuple[int, Optional[dict], str]:
    """发起 JSON 请求，返回 (status_code, 解析后的 json 或 None, 原始文本)"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:  # noqa: BLE001 —— 超时/连接拒绝等
        return 0, None, f"{type(e).__name__}: {e}"

    try:
        return status, json.loads(raw), raw
    except json.JSONDecodeError:
        return status, None, raw


def percentile(values: list[float], p: float) -> float:
    """线性插值分位数（p 取 0~100）"""
    if not values:
        return 0.0
    data = sorted(values)
    if len(data) == 1:
        return data[0]
    k = (len(data) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return data[int(k)]
    return data[lo] + (data[hi] - data[lo]) * (k - lo)


# ============================================================
# 单次调用
# ============================================================


@dataclass
class Result:
    scenario: str
    index: int
    ok: bool
    elapsed: float
    failure_kind: str = ""
    failure_detail: str = ""
    stage_reached: str = ""


def _friendly_failure(detail: str, limit: int = 70) -> str:
    text = " ".join(str(detail).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def call_once_task(
    base_url: str,
    text: str,
    user_id: str,
    timeout: float,
    poll_interval: float,
) -> tuple[bool, str, str, str]:
    """任务式调用：创建任务 + 轮询到结束。返回 (是否成功, 失败类别, 失败详情, 最后阶段)"""
    status, body, raw = http_json(
        "POST", f"{base_url}/api/complaint/task", {"text": text, "user_id": user_id}, timeout=timeout
    )
    if status == 0:
        return False, "连接失败", _friendly_failure(raw), ""
    if status != 200 or not isinstance(body, dict):
        return False, f"HTTP {status}", _friendly_failure(raw or f"HTTP {status}"), ""
    if body.get("code") != 0:
        return False, "业务错误", _friendly_failure(body.get("detail") or body), ""

    task_id = (body.get("data") or {}).get("task_id")
    if not task_id:
        return False, "响应异常", "创建任务未返回 task_id", ""

    deadline = time.time() + timeout
    stage = "排队中"
    # 先密后疏的轮询：刚提交时快速探测，避免把轮询间隔算进响应时间
    delay = 0.05
    while time.time() < deadline:
        s2, b2, raw2 = http_json("GET", f"{base_url}/api/complaint/task/{task_id}", timeout=timeout)
        if s2 == 0:
            return False, "轮询连接失败", _friendly_failure(raw2), stage
        if s2 != 200 or not isinstance(b2, dict):
            return False, f"轮询 HTTP {s2}", _friendly_failure(raw2 or f"HTTP {s2}"), stage
        if b2.get("code") != 0:
            return False, "轮询业务错误", _friendly_failure(b2.get("detail") or b2), stage
        data = b2.get("data") or {}
        stage = data.get("stage") or stage
        if data.get("status") == "done":
            if data.get("result"):
                return True, "", "", stage
            return False, "结果为空", "任务完成但 result 为空", stage
        if data.get("status") == "error":
            return False, "任务执行错误", _friendly_failure(data.get("error") or "未知错误"), stage
        time.sleep(delay)
        delay = min(delay * 2, poll_interval)
    return False, "超时", f"超过 {timeout:.0f}s 未完成（最后阶段：{stage}）", stage


def call_once_sync(
    base_url: str,
    text: str,
    user_id: str,
    timeout: float,
) -> tuple[bool, str, str, str]:
    """同步调用：POST /api/complaint/text"""
    status, body, raw = http_json(
        "POST", f"{base_url}/api/complaint/text", {"text": text, "user_id": user_id}, timeout=timeout
    )
    if status == 0:
        return False, "连接失败", _friendly_failure(raw), ""
    if status != 200 or not isinstance(body, dict):
        return False, f"HTTP {status}", _friendly_failure(raw or f"HTTP {status}"), ""
    if body.get("code") != 0:
        return False, "业务错误", _friendly_failure(body.get("detail") or body), ""
    if not (body.get("data") or {}).get("complaint_letter"):
        return False, "结果为空", "返回结果缺少 complaint_letter", ""
    return True, "", "", "完成"


def run_scenario(
    base_url: str,
    scenario_key: str,
    text: str,
    repeat: int,
    mode: str,
    timeout: float,
    poll_interval: float,
    stop_flag: threading.Event,
    progress: "Progress",
) -> list[Result]:
    """单个场景内部连续调用 repeat 次"""
    results: list[Result] = []
    run_id = uuid.uuid4().hex[:8]
    for i in range(1, repeat + 1):
        if stop_flag.is_set():
            break
        # 每次请求独立 user_id，避免触发每用户 10 次免费额度（压测专用）
        user_id = f"bench_{scenario_key}_{run_id}_{i}"
        started = time.perf_counter()
        if mode == "task":
            ok, kind, detail, stage = call_once_task(base_url, text, user_id, timeout, poll_interval)
        else:
            ok, kind, detail, stage = call_once_sync(base_url, text, user_id, timeout)
        elapsed = time.perf_counter() - started
        results.append(
            Result(
                scenario=scenario_key,
                index=i,
                ok=ok,
                elapsed=elapsed,
                failure_kind=kind,
                failure_detail=detail,
                stage_reached=stage,
            )
        )
        progress.tick(scenario_key, ok, elapsed)
    return results


# ============================================================
# 进度显示
# ============================================================


@dataclass
class Progress:
    total: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    done: int = 0
    ok: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    def tick(self, scenario: str, ok: bool, elapsed: float) -> None:
        with self.lock:
            self.done += 1
            if ok:
                self.ok += 1
            if self.done % 10 == 0 or self.done == self.total:
                elapsed_all = time.perf_counter() - self.started_at
                rate = self.done / elapsed_all if elapsed_all > 0 else 0
                print(
                    f"  [{self.done}/{self.total}] 成功 {self.ok} · "
                    f"最近一次 {scenario} {elapsed:.2f}s · 平均 {rate:.1f} req/s",
                    flush=True,
                )


# ============================================================
# 报告生成
# ============================================================


def summarize(results: list[Result]) -> dict:
    ok_results = [r for r in results if r.ok]
    latencies = [r.elapsed for r in ok_results]
    all_latencies = [r.elapsed for r in results]
    return {
        "total": len(results),
        "success": len(ok_results),
        "success_rate": (len(ok_results) / len(results) * 100) if results else 0.0,
        "avg": statistics.fmean(latencies) if latencies else 0.0,
        "p50": percentile(latencies, 50),
        "p95": percentile(latencies, 95),
        "p99": percentile(latencies, 99),
        "min": min(latencies) if latencies else 0.0,
        "max": max(all_latencies) if all_latencies else 0.0,
    }


def failure_distribution(results: list[Result]) -> list[tuple[str, int]]:
    counter: dict[str, int] = {}
    for r in results:
        if r.ok:
            continue
        key = f"{r.failure_kind}：{r.failure_detail}" if r.failure_detail else r.failure_kind
        counter[key] = counter.get(key, 0) + 1
    return sorted(counter.items(), key=lambda kv: -kv[1])


def render_report(
    results: list[Result],
    meta: dict,
    args: argparse.Namespace,
    wall_seconds: float,
    partial: bool,
) -> str:
    overall = summarize(results)
    by_scenario: dict[str, list[Result]] = {}
    for r in results:
        by_scenario.setdefault(r.scenario, []).append(r)

    scenario_titles = {key: idx + 1 for idx, (key, _) in enumerate(SCENARIOS)}
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_label = "演示模式（纯规则管线，无外部调用）" if meta.get("demo_mode") else "LLM 模式（调用大模型）"

    lines: list[str] = []
    lines.append("# 言权后端压测报告")
    lines.append("")
    lines.append(f"- 生成时间：{started}")
    lines.append(f"- 目标地址：`{args.base_url}`")
    lines.append(f"- 后端版本：`{meta.get('version', '未知')}`")
    lines.append(f"- 运行模式：{mode_label}")
    lines.append(f"- 调用方式：`{'POST /api/complaint/task + 轮询（端到端）' if args.mode == 'task' else 'POST /api/complaint/text（同步）'}`")
    lines.append(f"- 场景数：{len(by_scenario)} 个 · 每场景调用：{args.repeat} 次 · 总请求：{len(results)} 次")
    lines.append(f"- 场景间并发：{args.concurrency}（每个场景内部按顺序连续调用）")
    lines.append(f"- 单请求超时：{args.timeout:.0f}s · 轮询间隔：{args.poll_interval}s")
    lines.append(f"- 总耗时：{wall_seconds:.1f}s（{len(results) / wall_seconds:.2f} req/s）")
    lines.append(f"- 压测机环境：{platform.system()} {platform.release()} · Python {platform.python_version()}")
    if partial:
        lines.append("- ⚠️ 本次为**提前终止的部分结果**（触达 --max-seconds 上限），未覆盖全部计划请求")
    lines.append("")
    lines.append("> 说明：每次请求使用独立的合成 `user_id`，以免命中后端「每用户 10 次免费生成」的额度限制；"
                 "这是压测脚本的刻意设计，真实额度逻辑由 `backend/tests/test_api.py` 覆盖。")
    lines.append("")

    lines.append("## 一、总体结果")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 总请求数 | {overall['total']} |")
    lines.append(f"| 成功数 | {overall['success']} |")
    lines.append(f"| **成功率** | **{overall['success_rate']:.1f}%** |")
    lines.append(f"| 平均响应时间 | {overall['avg']:.2f}s |")
    lines.append(f"| P50 | {overall['p50']:.2f}s |")
    lines.append(f"| P95 | {overall['p95']:.2f}s |")
    lines.append(f"| P99 | {overall['p99']:.2f}s |")
    lines.append(f"| 最快 / 最慢 | {overall['min']:.2f}s / {overall['max']:.2f}s |")
    lines.append("")

    lines.append("## 二、分场景结果")
    lines.append("")
    lines.append("| # | 场景 | 请求数 | 成功率 | 平均 | P95 | P99 | 最慢 |")
    lines.append("|---|------|--------|--------|------|-----|-----|------|")
    for key in sorted(by_scenario.keys(), key=lambda k: scenario_titles.get(k, 99)):
        s = summarize(by_scenario[key])
        lines.append(
            f"| {scenario_titles.get(key, '-')} | {key} | {s['total']} | {s['success_rate']:.1f}% | "
            f"{s['avg']:.2f}s | {s['p95']:.2f}s | {s['p99']:.2f}s | {s['max']:.2f}s |"
        )
    lines.append("")

    lines.append("## 三、失败原因分布")
    lines.append("")
    dist = failure_distribution(results)
    if not dist:
        lines.append("本次压测没有失败请求。")
    else:
        lines.append("| 失败原因 | 次数 | 占比 |")
        lines.append("|----------|------|------|")
        for reason, count in dist:
            lines.append(f"| {reason} | {count} | {count / len(results) * 100:.1f}% |")
    lines.append("")

    lines.append("## 四、结论与建议")
    lines.append("")
    if not dist:
        lines.append(f"- 全部 {overall['total']} 次请求成功，服务在该并发下表现稳定。")
    else:
        lines.append(f"- 成功率 {overall['success_rate']:.1f}%，失败集中在：{dist[0][0]}（{dist[0][1]} 次）。")
    if overall["p95"] > 0:
        tail = "" if overall["p99"] <= overall["p95"] * 1.5 else "P99 明显高于 P95，通常是容器冷启动或模型调用抖动导致的尾部延迟。"
        lines.append(f"- P95 为 {overall['p95']:.2f}s、P99 为 {overall['p99']:.2f}s。{tail}".rstrip())
    if meta.get("demo_mode"):
        lines.append("- 本次为演示模式（规则管线），可用来验证接口稳定性与并发承载；"
                     "要评估真实 AI 生成耗时，请配置 API Key 后再跑一次 LLM 模式（注意调用成本）。")
    else:
        lines.append("- 本次为 LLM 模式，耗时包含大模型调用；如需对比，可关闭 API Key 再跑一次演示模式作为基线。")
    lines.append("")

    lines.append("## 五、复现方式")
    lines.append("")
    lines.append("```bash")
    lines.append("# 启动后端（另开一个终端）")
    lines.append("bash backend/run.sh")
    lines.append("")
    lines.append("# 运行压测（rag_env 环境，避免污染 base）")
    lines.append(f"/opt/anaconda3/envs/rag_env/bin/python scripts/benchmark.py --repeat {args.repeat} "
                 f"--concurrency {args.concurrency} --mode {args.mode}")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


# ============================================================
# 主流程
# ============================================================


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="言权后端批量压测")
    parser.add_argument("--base-url", default=os.environ.get("YANQUAN_BASE_URL", "http://127.0.0.1:8000"),
                        help="后端地址（默认 http://127.0.0.1:8000）")
    parser.add_argument("--mode", choices=["task", "sync"], default="task",
                        help="task：任务式+轮询（默认，端到端）；sync：同步接口")
    parser.add_argument("--repeat", type=int, default=100, help="每个场景调用次数（默认 100）")
    parser.add_argument("--scenarios", type=int, default=len(SCENARIOS),
                        help=f"使用前 N 个场景（默认 {len(SCENARIOS)} 个）")
    parser.add_argument("--concurrency", type=int, default=4, help="场景间并发数（默认 4）")
    parser.add_argument("--timeout", type=float, default=120.0, help="单请求超时秒数（默认 120）")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="任务轮询最大间隔秒数（默认 1.0，早期自动加密轮询）")
    parser.add_argument("--max-seconds", type=float, default=0.0,
                        help="整体时间上限（秒），0 表示不限；到点后停止发新请求并给出部分结果")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="markdown 报告输出路径")
    parser.add_argument("--allow-cost", action="store_true",
                        help="LLM 模式下请求数 > 50 时必须显式加此参数，确认愿意承担调用成本")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    base_url = args.base_url.rstrip("/")
    scenarios = SCENARIOS[: max(1, min(args.scenarios, len(SCENARIOS)))]
    total_requests = len(scenarios) * args.repeat

    # ---------- 探活 + 读取后端模式 ----------
    status, body, raw = http_json("GET", f"{base_url}/api/meta", timeout=15)
    if status != 200 or not isinstance(body, dict) or body.get("code") != 0:
        print(f"✗ 无法连接后端 {base_url}/api/meta（HTTP {status}）：{_friendly_failure(raw, 120)}", file=sys.stderr)
        print("  请先运行：bash backend/run.sh", file=sys.stderr)
        return 2
    meta = body.get("data") or {}

    print("言权后端压测")
    print(f"  目标：{base_url}  版本：{meta.get('version', '未知')}  "
          f"模式：{'demo（规则管线）' if meta.get('demo_mode') else 'llm（调用大模型）'}")
    print(f"  计划：{len(scenarios)} 个场景 × {args.repeat} 次 = {total_requests} 次请求，"
          f"场景间并发 {args.concurrency}")

    # ---------- 成本保护 ----------
    if not meta.get("demo_mode") and total_requests > 50 and not args.allow_cost:
        print(f"\n⚠️ 后端当前是 LLM 模式，{total_requests} 次请求会真实调用大模型并产生费用。", file=sys.stderr)
        print("   确认要继续请加 --allow-cost；或先用演示模式压测（清空 backend/.env 的 DASHSCOPE_API_KEY）。", file=sys.stderr)
        return 3

    # ---------- 执行 ----------
    stop_flag = threading.Event()
    progress = Progress(total=total_requests)
    started = time.perf_counter()
    results: list[Result] = []
    partial = False

    def worker(scenario_key: str, text: str) -> list[Result]:
        return run_scenario(base_url, scenario_key, text, args.repeat, args.mode,
                           args.timeout, args.poll_interval, stop_flag, progress)

    try:
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            futures = {pool.submit(worker, key, text): key for key, text in scenarios}
            for future in futures:
                if args.max_seconds and (time.perf_counter() - started) > args.max_seconds:
                    stop_flag.set()
                    partial = True
                try:
                    results.extend(future.result())
                except Exception as e:  # noqa: BLE001
                    print(f"  ✗ 场景 {futures[future]} 执行异常：{type(e).__name__}: {e}", file=sys.stderr)
                    partial = True
    except KeyboardInterrupt:
        stop_flag.set()
        partial = True
        print("\n已手动中断，输出部分结果…", file=sys.stderr)

    wall = time.perf_counter() - started
    if args.max_seconds and wall > args.max_seconds:
        partial = True

    # ---------- 报告 ----------
    report = render_report(results, meta, args, wall, partial)
    output_path = args.output if os.path.isabs(args.output) else os.path.join(REPO_ROOT, args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    overall = summarize(results)
    print("\n完成")
    print(f"  请求：{overall['total']}  成功：{overall['success']}  "
          f"成功率：{overall['success_rate']:.1f}%")
    print(f"  平均：{overall['avg']:.2f}s  P95：{overall['p95']:.2f}s  P99：{overall['p99']:.2f}s")
    print(f"  总耗时：{wall:.1f}s")
    print(f"  报告：{output_path}")
    dist = failure_distribution(results)
    if dist:
        print("  主要失败原因：")
        for reason, count in dist[:5]:
            print(f"    - {reason} × {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
