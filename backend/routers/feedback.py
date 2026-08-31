"""用户反馈接口：生成结果的有用性评价与纠错"""

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from ..database import get_feedback_stats, save_feedback
from ..routers.complaint import _resolve_user_id

router = APIRouter(prefix="/api/feedback", tags=["反馈"])


class FeedbackRequest(BaseModel):
    complaint_id: int
    rating: str = "helpful"  # helpful / unhelpful
    comment: str = ""


@router.post("")
async def create_feedback(
    req: FeedbackRequest,
    user_id: str = "default_user",
    authorization: Optional[str] = Header(None),
):
    """保存用户对投诉信生成结果的反馈"""
    uid = _resolve_user_id(user_id, authorization)
    if req.rating not in ("helpful", "unhelpful"):
        return JSONResponse(status_code=400, content={"code": -1, "detail": "rating 只能为 helpful 或 unhelpful"})
    record = save_feedback(req.complaint_id, uid, req.rating, req.comment.strip())
    return {"code": 0, "data": {"id": record["id"], "rating": record["rating"]}}


@router.get("/stats")
async def feedback_stats():
    """反馈统计"""
    return {"code": 0, "data": get_feedback_stats()}
