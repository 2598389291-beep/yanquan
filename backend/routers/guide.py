"""维权指南接口"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..services.guide import get_guide_scenarios
from ..services.templates import get_common_templates
from ..services.cases import get_reference_cases
from ..services.decision import build_decision
from ..services.evidence_checklist import get_evidence_checklist, list_scenarios

router = APIRouter(prefix="/api/guide", tags=["指南"])


@router.get("/scenarios")
async def guide_scenarios():
    """返回 8 大常见维权场景的结构化指南（法律依据 / 步骤 / 技巧）"""
    return {"code": 0, "data": {"scenarios": get_guide_scenarios()}}

@router.get("/scenarios/decision")
async def scenario_decisions():
    """返回各场景的维权路径决策矩阵（协商/12315/消协/诉讼，适用情况/耗时/成本）"""
    scenarios = get_guide_scenarios()
    return {"code": 0, "data": {"decisions": {s["key"]: build_decision(s["key"]) for s in scenarios}}}


@router.get("/evidence-checklist")
async def evidence_checklist(scenario: str = "general"):
    """按场景返回证据收集清单（该留哪些证据、为什么、怎么留）"""
    return {"code": 0, "data": get_evidence_checklist(scenario)}


@router.get("/evidence-scenarios")
async def evidence_scenarios():
    """返回证据清单可选场景列表"""
    return {"code": 0, "data": {"scenarios": list_scenarios()}}


@router.get("/templates")
async def guide_templates():
    """返回高频纠纷的通用投诉模板（即用型，含官方入口链接）"""
    return {"code": 0, "data": {"templates": get_common_templates()}}

@router.get("/cases")
async def guide_cases():
    """返回脱敏维权案例参考（覆盖常见场景，供用户参考解决路径）"""
    return {"code": 0, "data": {"cases": get_reference_cases()}}

@router.get("/scenarios/{key}")
async def guide_scenario_detail(key: str):
    """返回单个场景详情"""
    for s in get_guide_scenarios():
        if s["key"] == key:
            return {"code": 0, "data": s}
    return JSONResponse(status_code=404, content={"code": -1, "detail": "场景不存在"})
