"""法律知识库接口（法条溯源）"""

from fastapi import APIRouter

from ..database import get_legal_knowledge
from ..services.legal import law_source_url

router = APIRouter(prefix="/api/laws", tags=["法律"])


@router.get("")
async def list_laws():
    """返回本地法律知识库全部条文（含官方来源链接）"""
    laws = get_legal_knowledge()
    for law in laws:
        law["source_url"] = law_source_url(law["law_name"])
        law["tags"] = __import__("json").loads(law["tags"])
    return {"code": 0, "data": {"laws": laws}}


@router.get("/stats")
async def law_stats():
    """法律知识库统计"""
    laws = get_legal_knowledge()
    names = {law["law_name"] for law in laws}
    return {"code": 0, "data": {"total": len(laws), "laws_count": len(names)}}
