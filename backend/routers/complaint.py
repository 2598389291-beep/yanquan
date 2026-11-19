"""投诉相关 API 路由：语音/文字生成、历史记录、详情、状态流转、统计、删除"""

import base64
import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import settings
from ..authz import require_roles
from ..database import (
    CASE_STATUS_LABELS, FREE_GENERATION_LIMIT, STATUS_LABELS, VALID_STATUSES,
    delete_complaint, get_case_by_id, get_case_events, get_case_sla_state,
    get_complaint_by_id, get_complaint_stats, get_complaints, get_usage,
    get_user_by_token, increment_usage, save_complaint, save_feedback, update_complaint_status,
)
import httpx

from ..services import task_manager
from ..services.asr import transcribe_audio
from ..services.complaint_generator import generate_complaint, generate_complaint_progressive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["投诉"])


# ---------- 请求体 ----------

class VoiceJsonRequest(BaseModel):
    audio_base64: str
    audio_name: str = "voice.wav"
    user_id: str = "default_user"
    order_info: Optional[dict] = None
    evidence: Optional[list] = None


class TextComplaintRequest(BaseModel):
    text: str
    user_id: str = "default_user"
    order_info: Optional[dict] = None
    # 维权证据列表：[{file_name, file_url, order_info}, ...]
    evidence: Optional[list] = None
    # 预留：外部法律 API（如北大法宝）预检索的条文
    pkulaw_legal_data: Optional[list] = None


# ---------- 错误响应 ----------

def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": -1, "detail": detail})


# ---------- 辅助 ----------

def _resolve_identity(user_id: str, authorization: Optional[str]) -> tuple:
    """根据 token 或直接传入的 user_id 确定用户身份，返回 (uid, 是否已认证)"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        user = get_user_by_token(token)
        if user:
            return str(user["id"]), True
    return user_id, False


def _resolve_user_id(user_id: str, authorization: Optional[str]) -> str:
    """兼容旧调用：仅返回 uid"""
    return _resolve_identity(user_id, authorization)[0]


def _quota_exceeded(used: int) -> JSONResponse:
    """免费次数用完的响应（code=4031 供前端识别）"""
    return JSONResponse(status_code=403, content={"code": 4031, "detail": f"免费生成次数已用完（{used}/{FREE_GENERATION_LIMIT}）"})


def _check_quota(user_id: str, authed: bool = False):
    """返回 (是否允许, 错误响应)。仅「已登录且为后台配置的管理员账号」不限次数"""
    if authed and settings.admin_user_id and user_id == settings.admin_user_id:
        return True, None
    used = get_usage(user_id)
    if used >= FREE_GENERATION_LIMIT:
        return False, _quota_exceeded(used)
    return True, None


def _try_extract_order_info(image: Optional[UploadFile]) -> dict:
    """如果有截图则 OCR 提取订单信息；失败返回空 dict"""
    if not image or not image.filename:
        return {}

    ext = image.filename.split(".")[-1].lower() if image.filename else ""
    if ext not in ("jpg", "jpeg", "png", "webp"):
        return {}

    os.makedirs(settings.upload_dir, exist_ok=True)
    tmp_path = os.path.join(settings.upload_dir, f"ocr_{uuid.uuid4().hex}.{ext}")
    try:
        content = image.file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        from ..routers.ocr import _extract_order_info
        return _extract_order_info(tmp_path)
    except Exception as e:
        logger.warning("订单截图 OCR 失败：%s", e)
        return {}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _build_response_data(record: dict, result: dict, raw_text: str, order_info: dict) -> dict:
    """构建统一响应结构"""
    response_data = {
        "id": record["id"],
        "raw_text": raw_text,
        "complaint_letter": result["complaint_letter"],
        "legal_basis": result["legal_basis"],
        "action_path": result["action_path"],
        "category": result["category"],
        "status": record["status"],
        "status_label": STATUS_LABELS.get(record["status"], record["status"]),
        "order_info": order_info,
        "evidence": json.loads(record.get("evidence") or "[]"),
        "created_at": record["created_at"],
    }
    for key in ("suggestions", "channel_advice", "negotiation_script", "merchant_qualification_advice", "legal_details"):
        value = result.get(key)
        if value:
            response_data[key] = value

    # 维权行动向导：给每个结果挂上分步行动清单 + 证据收集清单（纯规则，幂等）
    try:
        from ..services.action_guide import attach_action_guide
        attach_action_guide(response_data)
    except Exception as e:
        logger.warning("行动清单生成失败：%s", e)
    return response_data


def _parse_evidence(raw: Optional[str]) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ---------- 任务式生成（分阶段：先骨架后补全） ----------

def _download_audio(audio_url: str, audio_name: str) -> str:
    """从云存储临时链接下载音频到本地临时文件"""
    import tempfile
    ext = os.path.splitext(audio_name or "voice")[1] or ".mp3"
    filepath = tempfile.mktemp(suffix=ext)
    resp = httpx.get(audio_url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    with open(filepath, "wb") as f:
        f.write(resp.content)
    return filepath


def _run_text_task(task: dict, text: str, order_info: Optional[dict], evidence: Optional[list], uid: str):
    """后台执行文本生成任务：分阶段推进进度，完成后入库并计数"""
    def progress(stage: str, pct: float, skeleton: str = ""):
        task_manager.update(task, stage=stage, progress=pct, skeleton=skeleton or task.get("skeleton", ""))

    try:
        result = generate_complaint_progressive(text, order_info, evidence, progress)
        rec = save_complaint(
            user_id=uid, raw_text=text,
            complaint_letter=result["complaint_letter"],
            legal_basis=result.get("legal_basis", []),
            action_path=result.get("action_path", []),
            category=result.get("category", "其他"),
            order_info=order_info, evidence=evidence or [],
        )
        increment_usage(uid)
        task_manager.update(
            task, status="done", stage="完成", progress=1.0,
            result=_build_response_data(rec, result, text, order_info or {}),
        )
    except Exception as e:
        logger.exception("生成任务失败")
        task_manager.update(task, status="error", error=f"投诉信生成失败: {e}")


def _run_voice_task(task: dict, audio_path: str, order_info: Optional[dict], evidence: Optional[list], uid: str):
    """后台执行语音生成任务：ASR → 分阶段生成 → 入库计数"""
    try:
        text = transcribe_audio(audio_path)
        if not text:
            raise ValueError("未能识别到有效语音内容，请重试")
        _run_text_task(task, text, order_info, evidence, uid)
    except Exception as e:
        logger.exception("语音生成任务失败")
        task_manager.update(task, status="error", error=str(e))
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass


# ---------- 接口 ----------

@router.post("/complaint/voice-json")
async def complaint_voice_json(
    req: VoiceJsonRequest,
    authorization: Optional[str] = Header(None),
):
    """
    云调用版语音接口：音频以 Base64 传入（云调用不支持 multipart）

    与 /complaint/voice 完全同一条生成管线。
    """
    uid, authed = _resolve_identity(req.user_id, authorization)
    if not req.audio_base64:
        return _error(400, "音频数据为空")

    ok, quota_err = _check_quota(uid, authed)
    if not ok:
        return quota_err

    try:
        raw = base64.b64decode(req.audio_base64)
    except Exception:
        return _error(400, "音频数据不是有效的 Base64")
    if len(raw) > 6 * 1024 * 1024:
        return _error(400, "音频文件过大（最大 6MB）")

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(req.audio_name or "voice.wav")[1] or ".wav"
    filepath = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{ext}")
    with open(filepath, "wb") as f:
        f.write(raw)

    try:
        def _process() -> tuple:
            text = transcribe_audio(filepath)
            if not text:
                raise ValueError("未能识别到有效语音内容，请重试")
            res = generate_complaint(text, req.order_info)
            rec = save_complaint(
                user_id=uid, raw_text=text,
                complaint_letter=res["complaint_letter"],
                legal_basis=res["legal_basis"],
                action_path=res["action_path"],
                category=res["category"],
                order_info=req.order_info,
                evidence=req.evidence or [],
            )
            increment_usage(user_id=uid)
            return text, res, rec

        raw_text, result, record = await run_in_threadpool(_process)
    except ValueError as e:
        return _error(400, str(e))
    except RuntimeError as e:
        return _error(500, str(e))
    except Exception as e:
        logger.exception("语音(JSON)生成失败")
        return _error(500, f"投诉信生成失败: {str(e)}")
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass

    return {"code": 0, "data": _build_response_data(record, result, raw_text, req.order_info or {})}


@router.post("/complaint/voice")
async def complaint_voice(
    file: UploadFile = File(...),
    image: UploadFile = File(None),
    user_id: str = Form("default_user"),
    order_info: str = Form("{}"),
    evidence: str = Form("[]"),
    authorization: Optional[str] = Header(None),
):
    """
    上传语音（+ 可选截图/证据），生成投诉信

    流程：保存音频 → ASR 转文字 → 截图 OCR 提取订单信息 → 生成投诉信 → 入库
    """
    uid, authed = _resolve_identity(user_id, authorization)

    ok, quota_err = _check_quota(uid, authed)
    if not ok:
        return quota_err

    try:
        parsed_order_info = json.loads(order_info) if order_info else {}
    except json.JSONDecodeError:
        parsed_order_info = {}

    parsed_evidence = _parse_evidence(evidence)

    ocr_info = _try_extract_order_info(image)
    if ocr_info:
        ocr_info.update({k: v for k, v in parsed_order_info.items() if v})
        parsed_order_info = ocr_info

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = file.filename.split(".")[-1] if file.filename else "m4a"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(settings.upload_dir, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    try:
        try:
            # 语音转码/识别/生成均为同步阻塞操作，放入线程池避免卡住事件循环
            def _process() -> tuple:
                text = transcribe_audio(filepath)
                if not text:
                    raise ValueError("未能识别到有效语音内容，请重试")
                res = generate_complaint(text, parsed_order_info)
                rec = save_complaint(
                    user_id=uid,
                    raw_text=text,
                    complaint_letter=res["complaint_letter"],
                    legal_basis=res["legal_basis"],
                    action_path=res["action_path"],
                    category=res["category"],
                    order_info=parsed_order_info,
                    evidence=parsed_evidence,
                )
                increment_usage(user_id=uid)
                return text, res, rec

            raw_text, result, record = await run_in_threadpool(_process)
        except ValueError as e:
            return _error(400, str(e))
        except RuntimeError as e:
            return _error(500, str(e))
        return {"code": 0, "data": _build_response_data(record, result, raw_text, parsed_order_info)}
    except Exception as e:
        logger.exception("语音生成失败")
        return _error(500, f"投诉信生成失败: {str(e)}")
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass


@router.post("/complaint/text")
async def complaint_text(
    req: TextComplaintRequest,
    authorization: Optional[str] = Header(None),
):
    """文本输入生成投诉信（语音的兜底方案），支持附带维权证据"""
    if not req.text.strip():
        return _error(400, "请输入维权经历")

    uid, authed = _resolve_identity(req.user_id, authorization)

    ok, quota_err = _check_quota(uid, authed)
    if not ok:
        return quota_err

    try:
        def _process() -> tuple:
            res = generate_complaint(req.text, req.order_info)
            rec = save_complaint(
                user_id=uid,
                raw_text=req.text,
                complaint_letter=res["complaint_letter"],
                legal_basis=res["legal_basis"],
                action_path=res["action_path"],
                category=res["category"],
                order_info=req.order_info,
                evidence=req.evidence or [],
            )
            increment_usage(user_id=uid)
            return res, rec

        result, record = await run_in_threadpool(_process)
    except Exception as e:
        logger.exception("文本生成失败")
        return _error(500, f"投诉信生成失败: {str(e)}")

    return {"code": 0, "data": _build_response_data(record, result, req.text, req.order_info or {})}


@router.get("/usage")
async def usage(
    user_id: str = "default_user",
    authorization: Optional[str] = Header(None),
):
    """查询当前用户免费生成次数使用情况"""
    uid, authed = _resolve_identity(user_id, authorization)
    used = get_usage(uid)
    return {"code": 0, "data": {
        "total": FREE_GENERATION_LIMIT,
        "used": used,
        "remaining": max(0, FREE_GENERATION_LIMIT - used),
        "unlimited": authed and uid == settings.admin_user_id,
    }}


class TranscribeRequest(BaseModel):
    audio_url: str = ""
    audio_base64: str = ""
    audio_name: str = "voice.mp3"


@router.post("/complaint/transcribe")
async def transcribe(req: TranscribeRequest):
    """仅语音转文字（不生成投诉信，不消耗免费次数）：转写后交用户确认修改再生成"""
    audio_path = None
    try:
        if req.audio_url:
            audio_path = _download_audio(req.audio_url, req.audio_name)
        elif req.audio_base64:
            raw = base64.b64decode(req.audio_base64)
            if len(raw) > 15 * 1024 * 1024:
                return _error(400, "音频文件过大（base64 最大 15MB）")
            import tempfile
            ext = os.path.splitext(req.audio_name or "voice.mp3")[1] or ".mp3"
            audio_path = tempfile.mktemp(suffix=ext)
            with open(audio_path, "wb") as f:
                f.write(raw)
        else:
            return _error(400, "请提供音频（audio_url 或 audio_base64）")

        text = await run_in_threadpool(transcribe_audio, audio_path)
        if not text:
            return _error(400, "未能识别到有效语音内容，请重试")
        return {"code": 0, "data": {"text": text}}
    except ValueError as e:
        return _error(400, str(e))
    except Exception as e:
        logger.exception("语音转写失败")
        return _error(500, f"语音识别失败: {e}")
    finally:
        try:
            if audio_path:
                os.remove(audio_path)
        except OSError:
            pass


class TaskTextRequest(BaseModel):
    text: str
    user_id: str = "default_user"
    order_info: Optional[dict] = None
    evidence: Optional[list] = None


class TaskVoiceRequest(BaseModel):
    audio_url: str = ""          # 云存储临时链接（推荐，绕开云调用 100KB 限制）
    audio_base64: str = ""       # 兜底：base64 音频（仅短音频可用）
    audio_name: str = "voice.mp3"
    user_id: str = "default_user"
    order_info: Optional[dict] = None
    evidence: Optional[list] = None


@router.post("/complaint/task")
async def create_text_task(
    req: TaskTextRequest,
    authorization: Optional[str] = Header(None),
):
    """创建文本生成任务：立即返回 task_id，前端轮询 /complaint/task/{id} 获取骨架与结果"""
    if not req.text.strip():
        return _error(400, "请输入维权经历")
    uid, authed = _resolve_identity(req.user_id, authorization)
    ok, quota_err = _check_quota(uid, authed)
    if not ok:
        return quota_err

    task = {"user_id": uid, "order_info": req.order_info or {}, "evidence": req.evidence or [], "text": req.text}
    task_id = task_manager.create_task(lambda t: _run_text_task(t, req.text, req.order_info or {}, req.evidence or [], uid))
    return {"code": 0, "data": {"task_id": task_id}}


@router.post("/complaint/task/voice")
async def create_voice_task(
    req: TaskVoiceRequest,
    authorization: Optional[str] = Header(None),
):
    """创建语音生成任务：audio_url 为云存储临时链接（推荐），audio_base64 仅兜底短音频"""
    uid, authed = _resolve_identity(req.user_id, authorization)
    ok, quota_err = _check_quota(uid, authed)
    if not ok:
        return quota_err

    audio_path = None
    try:
        if req.audio_url:
            audio_path = _download_audio(req.audio_url, req.audio_name)
        elif req.audio_base64:
            raw = base64.b64decode(req.audio_base64)
            if len(raw) > 15 * 1024 * 1024:
                return _error(400, "音频文件过大（base64 最大 15MB）")
            import tempfile
            ext = os.path.splitext(req.audio_name or "voice.mp3")[1] or ".mp3"
            audio_path = tempfile.mktemp(suffix=ext)
            with open(audio_path, "wb") as f:
                f.write(raw)
        else:
            return _error(400, "请提供音频（audio_url 或 audio_base64）")
    except Exception as e:
        return _error(400, f"音频获取失败: {e}")

    task_id = task_manager.create_task(
        lambda t: _run_voice_task(t, audio_path, req.order_info or {}, req.evidence or [], uid)
    )
    return {"code": 0, "data": {"task_id": task_id}}


@router.get("/complaint/task/{task_id}")
async def get_task_status(task_id: str):
    """轮询任务状态：stage/progress/skeleton/result"""
    task = task_manager.get_task(task_id)
    if not task:
        return _error(404, "任务不存在或已过期")
    return {"code": 0, "data": {
        "task_id": task["id"],
        "status": task["status"],
        "stage": task["stage"],
        "progress": task["progress"],
        "skeleton": task["skeleton"],
        "result": task["result"],
        "error": task["error"],
    }}


@router.get("/complaints")
async def list_complaints(
    user_id: str = "default_user",
    page: int = 1,
    page_size: int = 20,
    status: str = "all",
    authorization: Optional[str] = Header(None),
):
    """投诉记录列表（支持状态筛选）"""
    uid = _resolve_user_id(user_id, authorization)
    offset = (page - 1) * page_size
    try:
        items, total = get_complaints(uid, limit=page_size, offset=offset, status=status)
        for item in items:
            item["status_label"] = STATUS_LABELS.get(item.get("status", ""), item.get("status", ""))
    except Exception as e:
        return _error(500, f"查询失败: {str(e)}")

    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/complaints/stats")
async def complaint_stats(
    user_id: str = "default_user",
    authorization: Optional[str] = Header(None),
):
    """用户投诉统计（我的页）"""
    uid = _resolve_user_id(user_id, authorization)
    try:
        stats = get_complaint_stats(uid)
    except Exception as e:
        return _error(500, f"查询失败: {str(e)}")
    return {"code": 0, "data": stats}


@router.get("/complaint/{complaint_id}")
async def complaint_detail(complaint_id: int):
    """单条投诉详情"""
    try:
        record = get_complaint_by_id(complaint_id)
    except Exception as e:
        return _error(500, f"查询失败: {str(e)}")

    if not record:
        return _error(404, "投诉记录不存在")

    return {
        "code": 0,
        "data": {
            "id": record["id"],
            "raw_text": record["raw_text"],
            "complaint_letter": record["complaint_letter"],
            "legal_basis": json.loads(record["legal_basis"]),
            "action_path": json.loads(record["action_path"]),
            "category": record["category"],
            "status": record["status"],
            "status_label": STATUS_LABELS.get(record["status"], record["status"]),
            "order_info": json.loads(record["order_info"]) if record["order_info"] else {},
            "evidence": json.loads(record["evidence"]) if record.get("evidence") else [],
            "created_at": record["created_at"],
        },
    }


@router.get("/complaint/{complaint_id}/progress")
async def complaint_progress(
    complaint_id: int,
    owner: dict = Depends(require_roles("consumer", "agent", "admin")),
):
    """用户查看案件处理进度与客服操作轨迹（仅案件归属人）。"""
    case = get_case_by_id(complaint_id)
    if not case or str(case.get("user_id")) != str(owner["id"]):
        return _error(404, "投诉记录不存在或无权限查看")
    events = get_case_events(complaint_id)
    public_actions = {
        "claimed": "客服已认领",
        "assigned": "案件已分派",
        "status_changed": "处理进度已更新",
    }
    assignee_name = (
        case.get("assignee_nickname") or "客服人员"
        if case.get("assignee_id")
        else ""
    )
    return {
        "code": 0,
        "data": {
            "id": complaint_id,
            "case_status": case["case_status"],
            "case_status_label": CASE_STATUS_LABELS.get(
                case["case_status"], case["case_status"]
            ),
            "assignee_name": assignee_name,
            "sla_due_at": case.get("sla_due_at") or "",
            "sla_state": get_case_sla_state(case),
            "events": [
                {
                    "action": event["action"],
                    "label": public_actions.get(event["action"], "案件状态已更新"),
                    "case_status": event["to_case_status"],
                    "case_status_label": CASE_STATUS_LABELS.get(
                        event["to_case_status"], event["to_case_status"]
                    ),
                    "created_at": event["created_at"],
                }
                for event in events
            ],
        },
    }


class StatusUpdateRequest(BaseModel):
    status: str
    user_id: str = "default_user"


@router.api_route("/complaint/{complaint_id}/status", methods=["PATCH", "POST"])
async def update_status(
    complaint_id: int,
    req: Optional[StatusUpdateRequest] = None,
    status: Optional[str] = None,
    user_id: str = "default_user",
    authorization: Optional[str] = Header(None),
):
    """更新投诉记录状态（PATCH query 或 POST body 均兼容）"""
    if req is not None:
        status = req.status
        user_id = req.user_id or user_id
    if not status:
        return _error(400, "缺少 status 参数")

    uid = _resolve_user_id(user_id, authorization)

    if status not in VALID_STATUSES:
        return _error(400, f"无效状态值，有效值：{', '.join(VALID_STATUSES)}")

    try:
        updated = update_complaint_status(complaint_id, uid, status)
    except ValueError as e:
        return _error(400, str(e))
    except Exception as e:
        return _error(500, f"状态更新失败: {str(e)}")

    if not updated:
        return _error(404, "投诉记录不存在或无权限操作")

    return {"code": 0, "data": {
        "id": updated["id"],
        "status": updated["status"],
        "status_label": STATUS_LABELS.get(updated["status"], updated["status"]),
    }}


class DeleteRequest(BaseModel):
    user_id: str = "default_user"


def _remove(complaint_id: int, user_id: str, authorization: Optional[str]):
    uid = _resolve_user_id(user_id, authorization)
    try:
        ok = delete_complaint(complaint_id, uid)
    except Exception as e:
        return _error(500, f"删除失败: {str(e)}")
    if not ok:
        return _error(404, "投诉记录不存在或无权限操作")
    return {"code": 0, "data": {"deleted": True}}


@router.delete("/complaint/{complaint_id}")
async def remove_complaint(
    complaint_id: int,
    user_id: str = "default_user",
    authorization: Optional[str] = Header(None),
):
    """删除投诉记录（归属校验）"""
    return _remove(complaint_id, user_id, authorization)


class OutcomeRequest(BaseModel):
    outcome: str  # resolved / partial / unresolved / no_response


@router.post("/complaint/{complaint_id}/outcome")
async def report_outcome(
    complaint_id: int,
    req: OutcomeRequest,
    user_id: str = "default_user",
    authorization: Optional[str] = Header(None),
):
    """轻回访：记录纠纷最终处理结果（不打扰，一次即可）"""
    if req.outcome not in ("resolved", "partial", "unresolved", "no_response"):
        return _error(400, "无效的处理结果")
    uid = _resolve_user_id(user_id, authorization)
    try:
        record = get_complaint_by_id(complaint_id)
        if not record:
            return _error(404, "记录不存在")
        save_feedback(complaint_id=complaint_id, user_id=uid, rating="outcome", comment=req.outcome)
    except Exception as e:
        return _error(500, f"提交失败: {e}")
    return {"code": 0, "data": {"message": "感谢反馈，我们会用真实数据持续优化"}}


@router.post("/complaint/{complaint_id}/delete")
async def remove_complaint_post(
    complaint_id: int,
    req: Optional[DeleteRequest] = None,
    user_id: str = "default_user",
    authorization: Optional[str] = Header(None),
):
    """删除投诉记录（云调用 POST 版）"""
    if req is not None:
        user_id = req.user_id or user_id
    return _remove(complaint_id, user_id, authorization)
