"""客服运营端：案件队列、认领、分派、状态流转与操作日志。"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..authz import require_roles
from ..database import (
    CASE_STATUS_LABELS,
    STATUS_LABELS,
    assign_case,
    claim_case,
    get_case_by_id,
    get_case_sla_state,
    get_operations_summary,
    get_user_by_id,
    list_agents,
    list_cases,
    save_case_suggestion,
    set_user_role,
    transition_case,
    update_case_triage,
)
from ..services.triage import triage_case
from ..services.reply_suggestion import build_reply_suggestion

router = APIRouter(prefix="/api/operations", tags=["客服运营"])


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": -1, "detail": detail})


def _json_value(raw, default):
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _can_view_case(case: dict, actor: dict) -> bool:
    if actor["role"] == "admin":
        return True
    assignee_id = case.get("assignee_id") or ""
    return not assignee_id or assignee_id == str(actor["id"])


def _serialize_case(case: dict, include_letter: bool = False) -> dict:
    data = {
        "id": case["id"],
        "user_id": case["user_id"],
        "raw_text": case["raw_text"],
        "category": case["category"],
        "status": case["status"],
        "status_label": STATUS_LABELS.get(case["status"], case["status"]),
        "case_status": case["case_status"],
        "case_status_label": CASE_STATUS_LABELS.get(
            case["case_status"], case["case_status"]
        ),
        "assignee_id": case.get("assignee_id") or "",
        "assignee_nickname": case.get("assignee_nickname") or "",
        "assignee_name": _assignee_name(case),
        "claimed_at": case.get("claimed_at") or "",
        "sla_due_at": case.get("sla_due_at") or "",
        "sla_state": get_case_sla_state(case),
        "created_at": case["created_at"],
        "legal_basis": _json_value(case.get("legal_basis"), []),
        "action_path": _json_value(case.get("action_path"), []),
        "order_info": _json_value(case.get("order_info"), {}),
        "evidence": _json_value(case.get("evidence"), []),
        "triage": {
            "category": case.get("triage_category") or "",
            "priority": case.get("triage_priority") or "",
            "team": case.get("triage_team") or "",
            "confidence": case.get("triage_confidence"),
            "reason": case.get("triage_reason") or "",
            "signals": _json_value(case.get("triage_signals"), []),
            "source": case.get("triage_source") or "",
            "triaged_at": case.get("triage_at") or "",
        },
        "reply_suggestion": {
            "reply": case.get("suggestion_text") or "",
            "citations": _json_value(case.get("suggestion_citations"), []),
            "next_actions": _json_value(case.get("suggestion_next_actions"), []),
            "risk_flags": _json_value(case.get("suggestion_risk_flags"), []),
            "source": case.get("suggestion_source") or "",
            "generated_at": case.get("suggestion_generated_at") or "",
        },
        "events": case.get("events") or [],
    }
    if include_letter:
        data["complaint_letter"] = case.get("complaint_letter", "")
    return data


def _assignee_name(case: dict) -> str:
    assignee_id = case.get("assignee_id") or ""
    if not assignee_id:
        return "未分配"
    return (
        case.get("assignee_nickname")
        or case.get("assignee_email")
        or case.get("assignee_phone")
        or f"账号 {assignee_id}"
    )


@router.get("/cases")
async def operations_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    case_status: str = "all",
    category: str = "",
    assignee_id: Optional[str] = None,
    priority: str = "all",
    q: str = "",
    actor: dict = Depends(require_roles("agent", "admin")),
):
    """运营案件列表；客服仅看到待认领和自己名下案件。"""
    offset = (page - 1) * page_size
    items, total = list_cases(
        actor_id=str(actor["id"]),
        actor_role=actor["role"],
        limit=page_size,
        offset=offset,
        case_status=case_status,
        category=category or None,
        assignee_id=assignee_id if actor["role"] == "admin" else None,
        priority=priority,
        query=q or None,
    )
    return {
        "code": 0,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/summary")
async def operations_summary(
    actor: dict = Depends(require_roles("agent", "admin")),
):
    """运营队列真实计数，不包含未实现的结案率或采纳率。"""
    return {
        "code": 0,
        "data": get_operations_summary(str(actor["id"]), actor["role"]),
    }


@router.get("/cases/{complaint_id}")
async def operations_case_detail(
    complaint_id: int,
    actor: dict = Depends(require_roles("agent", "admin")),
):
    case = get_case_by_id(complaint_id)
    if not case:
        return _error(404, "案件不存在")
    if not _can_view_case(case, actor):
        return _error(403, "该案件已由其他客服处理")
    return {"code": 0, "data": _serialize_case(case, include_letter=True)}


@router.post("/cases/{complaint_id}/claim")
async def claim_operations_case(
    complaint_id: int,
    actor: dict = Depends(require_roles("agent", "admin")),
):
    try:
        case = claim_case(complaint_id, str(actor["id"]))
    except ValueError as exc:
        return _error(409, str(exc))
    if not case:
        return _error(404, "案件不存在")
    return {"code": 0, "data": _serialize_case(case, include_letter=True)}


class AssignCaseRequest(BaseModel):
    assignee_id: str


@router.post("/cases/{complaint_id}/assign")
async def assign_operations_case(
    complaint_id: int,
    req: AssignCaseRequest,
    actor: dict = Depends(require_roles("admin")),
):
    try:
        case = assign_case(complaint_id, str(actor["id"]), req.assignee_id.strip())
    except ValueError as exc:
        return _error(400, str(exc))
    if not case:
        return _error(404, "案件不存在")
    return {"code": 0, "data": _serialize_case(case, include_letter=True)}


class CaseStatusRequest(BaseModel):
    case_status: str


@router.post("/cases/{complaint_id}/status")
async def update_operations_case_status(
    complaint_id: int,
    req: CaseStatusRequest,
    actor: dict = Depends(require_roles("agent", "admin")),
):
    existing = get_case_by_id(complaint_id)
    if not existing:
        return _error(404, "案件不存在")
    if not _can_view_case(existing, actor):
        return _error(403, "无权操作其他客服的案件")
    try:
        case = transition_case(complaint_id, str(actor["id"]), req.case_status)
    except ValueError as exc:
        return _error(400, str(exc))
    return {"code": 0, "data": _serialize_case(case, include_letter=True)}


@router.post("/cases/{complaint_id}/triage")
async def triage_operations_case(
    complaint_id: int,
    actor: dict = Depends(require_roles("agent", "admin")),
):
    existing = get_case_by_id(complaint_id)
    if not existing:
        return _error(404, "案件不存在")
    if not _can_view_case(existing, actor):
        return _error(403, "无权操作其他客服的案件")
    evidence = _json_value(existing.get("evidence"), [])
    order_info = _json_value(existing.get("order_info"), {})
    triage = triage_case(
        existing.get("raw_text", ""),
        existing_category=existing.get("category", ""),
        order_info=order_info,
        evidence=evidence,
    )
    case = update_case_triage(complaint_id, str(actor["id"]), triage)
    return {"code": 0, "data": _serialize_case(case, include_letter=True)}


@router.post("/cases/{complaint_id}/suggestion")
async def suggest_operations_reply(
    complaint_id: int,
    actor: dict = Depends(require_roles("agent", "admin")),
):
    existing = get_case_by_id(complaint_id)
    if not existing:
        return _error(404, "案件不存在")
    if not _can_view_case(existing, actor):
        return _error(403, "无权操作其他客服的案件")
    suggestion = build_reply_suggestion(
        existing.get("raw_text", ""),
        category=existing.get("triage_category") or existing.get("category", ""),
        evidence=_json_value(existing.get("evidence"), []),
    )
    case = save_case_suggestion(complaint_id, str(actor["id"]), suggestion)
    return {"code": 0, "data": _serialize_case(case, include_letter=True)}


@router.get("/agents")
async def operations_agents(actor: dict = Depends(require_roles("admin"))):
    """管理员分派时选择客服。"""
    return {"code": 0, "data": {"items": list_agents()}}


class RoleUpdateRequest(BaseModel):
    role: str


@router.post("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    req: RoleUpdateRequest,
    actor: dict = Depends(require_roles("admin")),
):
    """管理员维护消费者、客服、管理员三类角色。"""
    if not get_user_by_id(user_id):
        return _error(404, "用户不存在")
    if req.role not in ("consumer", "agent", "admin"):
        return _error(400, "role 只能为 consumer、agent 或 admin")
    user = set_user_role(user_id, req.role)
    return {
        "code": 0,
        "data": {
            "id": user["id"],
            "nickname": user.get("nickname", ""),
            "role": user["role"],
        },
    }
