"""维权证据接口：批量上传截图并 OCR 提取订单信息"""

import base64
import json
import logging
import os
import uuid

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence", tags=["证据"])

ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp"}


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": -1, "detail": detail})


class EvidenceJsonRequest(BaseModel):
    files: list[dict]  # [{name, base64}]
    user_id: str = "default_user"


def _make_item(filepath: str, file_name: str) -> dict:
    from ..routers.ocr import _extract_order_info
    try:
        order_info = _extract_order_info(filepath)
    except Exception as e:
        logger.warning("证据 OCR 失败：%s", e)
        order_info = {}
    file_base64 = ""
    try:
        with open(filepath, "rb") as f:
            file_base64 = base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        pass
    return {
        "file_name": file_name,
        "file_url": f"/files/evidence/{os.path.basename(filepath)}",
        "file_base64": file_base64,
        "order_info": order_info,
    }


@router.post("/upload-json")
async def upload_evidence_json(req: EvidenceJsonRequest):
    """
    云调用版证据上传：图片以 Base64 列表传入

    返回：[{ file_name, file_url, file_base64, order_info }, ...]
    """
    if not req.files:
        return _error(400, "请至少上传一张图片")
    if len(req.files) > 6:
        return _error(400, "最多上传 6 张证据图片")

    os.makedirs(settings.upload_dir, exist_ok=True)
    evidence_dir = os.path.join(settings.upload_dir, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    items = []
    for f in req.files:
        name = str(f.get("name") or "evidence.png")
        ext = os.path.splitext(name)[1].lower() or ".png"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            return _error(400, f"不支持的图片格式：{name}，请上传 JPG/PNG/WebP")
        try:
            data = base64.b64decode(str(f.get("base64") or ""))
        except Exception:
            return _error(400, f"图片 {name} 不是有效的 Base64")
        if len(data) > 3 * 1024 * 1024:
            return _error(400, f"图片 {name} 过大（单张最大 3MB）")

        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(evidence_dir, filename)
        with open(filepath, "wb") as fp:
            fp.write(data)
        items.append(_make_item(filepath, name))

    return {"code": 0, "data": {"items": items}}


@router.post("/upload")
async def upload_evidence(
    files: list[UploadFile] = File(...),
    user_id: str = Form("default_user"),
):
    """
    批量上传证据截图（订单/聊天/物流/支付凭证等），每张图 OCR 提取关键信息

    返回：[{ file_name, file_url, order_info: {...} }, ...]
    """
    if not files:
        return _error(400, "请至少上传一张图片")
    if len(files) > 6:
        return _error(400, "最多上传 6 张证据图片")

    os.makedirs(settings.upload_dir, exist_ok=True)
    evidence_dir = os.path.join(settings.upload_dir, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    from ..routers.ocr import _extract_order_info

    items = []
    for file in files:
        ext = file.filename.split(".")[-1].lower() if file.filename else "png"
        if ext not in ALLOWED_EXTS:
            return _error(400, f"不支持的图片格式：{file.filename}，请上传 JPG/PNG/WebP")

        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(evidence_dir, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        items.append(_make_item(filepath, file.filename or filename))

    return {"code": 0, "data": {"items": items}}
