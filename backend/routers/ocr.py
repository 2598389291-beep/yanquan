"""图片 OCR 识别 API（截图中提取订单信息，通义千问 VL 多模态）"""

import base64
import logging
import os
import uuid

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from openai import OpenAI

from ..config import settings
from ..services.llm import extract_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr", tags=["图片识别"])

ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp"}


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": -1, "detail": detail})


def _extract_order_info(image_path: str) -> dict:
    """使用通义千问 Vision 模型从截图中提取订单信息；演示模式返回空结构"""
    if settings.demo_mode:
        return {"platform": "", "order_number": "", "order_date": "", "product_name": "", "amount": "", "seller": ""}

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/png")

    client = OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.llm_base_url,
        timeout=60,
        max_retries=2,
    )

    prompt = """请从这张截图中提取以下订单信息，以 JSON 格式返回。如果某项信息在截图中找不到，请填写空字符串。
返回格式必须是严格的 JSON，不要包含任何其他文字：

{
    "platform": "电商平台名称（如拼多多、淘宝、京东、美团等）",
    "order_number": "订单号/交易单号",
    "order_date": "订单日期（格式 YYYY-MM-DD）",
    "product_name": "商品名称",
    "amount": "订单金额（纯数字，如 2000.00）",
    "seller": "商家/店铺名称"
}"""

    response = client.chat.completions.create(
        model="qwen-vl-max",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        max_tokens=1024,
    )

    raw = response.choices[0].message.content.strip()
    result = extract_json(raw)
    if not isinstance(result, dict):
        result = {}

    keys = ["platform", "order_number", "order_date", "product_name", "amount", "seller"]
    return {k: str(result.get(k, "")) for k in keys}


@router.post("/extract")
async def extract_order(
    file: UploadFile = File(...),
    user_id: str = Form("default_user"),
):
    """上传截图，提取订单信息（支持 JPG / PNG / WebP）"""
    ext = file.filename.split(".")[-1].lower() if file.filename else "png"
    if ext not in ALLOWED_EXTS:
        return _error(400, "不支持的图片格式，请上传 JPG/PNG/WebP 图片")

    os.makedirs(settings.upload_dir, exist_ok=True)
    filepath = os.path.join(settings.upload_dir, f"ocr_{uuid.uuid4().hex}.{ext}")
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    try:
        order_info = _extract_order_info(filepath)
    except Exception as e:
        logger.exception("OCR 识别失败")
        return _error(500, f"图片识别失败: {str(e)}")
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass

    return {"code": 0, "data": order_info}
