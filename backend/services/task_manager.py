"""生成任务管理器：分阶段异步生成，前端轮询进度，先出骨架再补全"""

import logging
import threading
import time
import uuid
from typing import Callable, Optional

logger = logging.getLogger(__name__)

TASKS: dict = {}
_LOCK = threading.Lock()
TASK_TTL_SECONDS = 60 * 60  # 任务 1 小时后清理


def create_task(runner: Callable[[dict], None]) -> str:
    """创建任务并后台执行。runner(task) 负责推进 task 状态。"""
    task_id = uuid.uuid4().hex[:12]
    task = {
        "id": task_id,
        "status": "running",       # running / done / error
        "stage": "排队中",
        "progress": 0.05,          # 0~1
        "skeleton": "",            # 骨架投诉信（先给用户看）
        "result": None,            # 完整结果
        "error": "",
        "created_at": time.time(),
    }
    with _LOCK:
        TASKS[task_id] = task
    thread = threading.Thread(target=_safe_run, args=(task, runner), daemon=True)
    thread.start()
    return task_id


def _safe_run(task: dict, runner: Callable[[dict], None]):
    try:
        runner(task)
    except Exception as e:  # noqa: BLE001
        logger.exception("生成任务执行失败 task=%s", task["id"])
        with _LOCK:
            task["status"] = "error"
            task["error"] = str(e)


def update(task: dict, **kwargs):
    with _LOCK:
        task.update(kwargs)


def get_task(task_id: str) -> Optional[dict]:
    with _LOCK:
        task = TASKS.get(task_id)
        return dict(task) if task else None


def cleanup_expired():
    now = time.time()
    with _LOCK:
        expired = [tid for tid, t in TASKS.items() if now - t["created_at"] > TASK_TTL_SECONDS]
        for tid in expired:
            del TASKS[tid]
