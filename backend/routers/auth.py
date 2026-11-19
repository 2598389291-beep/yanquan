"""用户认证 API（邮箱密码 + 微信小程序登录）"""

import asyncio
import hashlib
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import settings
from ..database import create_or_update_user, get_user_by_email, get_user_by_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])

WECHAT_API = "https://api.weixin.qq.com/sns/jscode2session"


# ---------- 请求体 ----------

class SendCodeRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str


class EmailLoginRequest(BaseModel):
    email: str
    password: str


class WechatLoginRequest(BaseModel):
    code: str
    nickname: str = ""
    avatar: str = ""


# ---------- 模拟验证码存储（生产环境应使用 Redis） ----------

_verification_codes: dict[str, dict] = {}
DEMO_CODE = "123456"


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": -1, "detail": detail})


def _validate_phone(phone: str) -> bool:
    return bool(re.match(r"^1[3-9]\d{9}$", phone))


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$", email))


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"pbkdf2_sha256$100000${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return secrets.compare_digest(calc, digest)
    except Exception:
        return False


async def _wechat_code2session(code: str) -> str:
    """调用微信 jscode2session 换 openid（25s 超时 + 2 次重试）"""
    last_err: object = None
    # 云托管容器出网可能经过代理链路（自签名证书），固定跳过证书校验并忽略代理环境变量
    if os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"):
        logger.warning("检测到代理环境变量：HTTP_PROXY=%s HTTPS_PROXY=%s",
                       os.environ.get("HTTP_PROXY"), os.environ.get("HTTPS_PROXY"))
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=25, verify=False) as client:
                resp = await client.get(
                    WECHAT_API,
                    params={
                        "appid": settings.wechat_appid,
                        "secret": settings.wechat_secret,
                        "js_code": code,
                        "grant_type": "authorization_code",
                    },
                )
                data = resp.json()
            if "openid" in data:
                return data["openid"]
            last_err = data
            logger.warning("微信登录失败（第%s次）：%s", attempt + 1, data)
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("微信登录网络异常（第%s次）：%s", attempt + 1, e)
            if attempt == 0:
                await asyncio.sleep(1.5)
    raise RuntimeError(last_err)


def _new_token() -> str:
    return uuid.uuid4().hex


def _login_response(user: dict) -> dict:
    return {
        "code": 0,
        "data": {
            "token": user["token"],
            "phone": user.get("phone", "") or "",
            "email": user.get("email", "") or "",
            "user_id": user["id"],
            "nickname": user.get("nickname", ""),
            "avatar": user.get("avatar", ""),
            "role": user.get("role") or "consumer",
            "expires_at": user.get("token_expires_at", ""),
        },
    }


# ---------- 接口 ----------

@router.post("/send-code")
async def send_code(req: SendCodeRequest):
    """发送短信验证码（演示环境固定 123456，不实际发送短信）"""
    phone = req.phone.strip()
    if not _validate_phone(phone):
        return _error(400, "请输入正确的手机号")

    if phone in _verification_codes:
        last_sent = _verification_codes[phone].get("sent_at", "")
        if last_sent:
            try:
                last_time = datetime.fromisoformat(last_sent)
                if datetime.now() - last_time < timedelta(seconds=60):
                    return _error(429, "验证码已发送，请60秒后再试")
            except ValueError:
                pass

    _verification_codes[phone] = {
        "code": DEMO_CODE,
        "sent_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(minutes=5)).isoformat(),
    }
    return {
        "code": 0,
        "data": {"phone": phone, "message": "验证码已发送（演示版本验证码为 123456）"},
    }


@router.post("/verify")
async def verify_code(req: VerifyCodeRequest):
    """验证验证码并登录（演示环境验证码固定 123456；生产接入短信服务商）"""
    phone = req.phone.strip()
    if not _validate_phone(phone):
        return _error(400, "请输入正确的手机号")

    stored = _verification_codes.get(phone)
    if not stored:
        return _error(400, "请先获取验证码")
    if stored["code"] != req.code:
        return _error(400, "验证码错误")

    user = create_or_update_user(phone=phone)
    _verification_codes.pop(phone, None)
    return _login_response(user)


@router.post("/email/login")
async def email_login(req: EmailLoginRequest):
    """邮箱密码登录：首次登录自动注册，已有账号校验密码"""
    email = req.email.strip().lower()
    if not _validate_email(email):
        return _error(400, "请输入正确的邮箱地址")
    if len(req.password) < 6:
        return _error(400, "密码至少 6 位")

    user = get_user_by_email(email)
    if user is None:
        user = create_or_update_user(email=email, password_hash=_hash_password(req.password))
        return _login_response(user)

    if not _verify_password(req.password, user.get("password_hash") or ""):
        return _error(401, "邮箱或密码错误")

    user = create_or_update_user(email=email, nickname=user.get("nickname", ""), avatar=user.get("avatar", ""))
    return _login_response(user)


@router.post("/wechat/login")
async def wechat_login(req: WechatLoginRequest):
    """
    微信小程序登录：code 换 openid

    - 已配置 WECHAT_APPID/SECRET：调用官方 jscode2session 接口
    - 未配置（演示/开发）：任意 code 视为有效，openid 由 code 派生
    """
    if not req.code.strip():
        return _error(400, "缺少微信登录 code")

    openid = ""
    if settings.wechat_appid and settings.wechat_secret:
        try:
            openid = await _wechat_code2session(req.code)
        except Exception as e:
            logger.exception("微信登录接口异常（请检查 WECHAT_APPID/SECRET 与容器出网）")
            return _error(502, "微信登录服务暂时不可用，请稍后重试")
    else:
        # 开发/演示模式：用 code 的哈希派生稳定 openid
        openid = "demo_" + uuid.uuid5(uuid.NAMESPACE_URL, req.code.strip()).hex[:28]

    user = create_or_update_user(openid=openid, nickname=req.nickname, avatar=req.avatar)
    return _login_response(user)
