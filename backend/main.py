"""言权（AI 消费者维权助手）后端入口"""

import logging
from contextlib import asynccontextmanager

from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import auth, complaint, evidence, feedback, guide, laws, ocr
from .database import get_legal_knowledge
from .services.guide import get_guide_scenarios
from .services.templates import get_common_templates
from .services.cases import get_reference_cases

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

APP_VERSION = "1.1.0"
APP_BUILD = "20260827-v1.2"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info(
        "启动完成：mode=%s env=%s llm=%s",
        "demo" if settings.demo_mode else "llm",
        settings.environment,
        settings.llm_model,
    )
    yield


app = FastAPI(
    title="言权 · AI 消费者维权助手",
    description="口述维权经历，AI 自动生成专业投诉信 + 法律依据 + 维权路径 + 沟通话术",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(complaint.router)
app.include_router(auth.router)
app.include_router(ocr.router)
app.include_router(guide.router)
app.include_router(laws.router)
app.include_router(evidence.router)
app.include_router(feedback.router)

# 证据图片静态访问（/files/evidence/xxx.png）
import os as _os
_os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=settings.upload_dir), name="files")


# ---------- 统一错误处理 ----------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"code": -1, "detail": "请求参数格式错误，请检查输入"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("未捕获异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": -1, "detail": "服务器内部错误，请稍后重试"},
    )


# ---------- 基础接口 ----------

@app.get("/")
def root():
    return {
        "name": "言权 · AI 消费者维权助手",
        "version": APP_VERSION,
        "docs": "/docs",
        "mode": "demo" if settings.demo_mode else "llm",
        "message": "口述即出信，维权有依据",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "build": APP_BUILD,
        "mode": "demo" if settings.demo_mode else "llm",
        "environment": settings.environment,
    }


@app.get("/api/meta")
def meta(authorization: Optional[str] = Header(None)):
    """小程序启动时拉取：运行模式 / 能力开关 / 版本号 / 管理员标记"""
    is_admin = False
    if authorization and authorization.startswith("Bearer "):
        from .database import get_user_by_token
        user = get_user_by_token(authorization[7:])
        if user and settings.admin_user_id and str(user["id"]) == settings.admin_user_id:
            is_admin = True
    return {
        "code": 0,
        "data": {
            "app_name": "言权",
            "slogan": "口述即出信，维权有依据",
            "version": APP_VERSION,
            "demo_mode": settings.demo_mode,
            "is_admin": is_admin,
            "features": {
                "voice": not settings.demo_mode,
                "ocr": not settings.demo_mode,
                "wechat_login": bool(settings.wechat_appid and settings.wechat_secret),
            },
            "stats": {
                "laws": len(get_legal_knowledge()),
                "scenarios": len(get_guide_scenarios()),
                "templates": len(get_common_templates()),
                "cases": len(get_reference_cases()),
            },
        },
    }
