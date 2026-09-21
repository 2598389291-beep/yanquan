"""项目配置（pydantic-settings，支持 .env / 环境变量覆盖）"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
_env_file = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """应用配置"""

    # ========== 核心服务 ==========
    # DashScope API Key（通义千问 + ASR + OCR）
    # 留空 / 填占位符时自动进入"演示模式"（纯规则生成，无需任何外部服务）
    dashscope_api_key: str = ""

    # 微信小程序（上线后必填，用于 jscode2session 登录）
    wechat_appid: str = ""
    wechat_secret: str = ""

    # ========== 运营 ==========
    # 开发者/管理员账号 ID（登录后的 user id）：此账号免费次数不限（其余用户不受影响）
    admin_user_id: str = ""

    # ========== 服务监听 ==========
    host: str = "0.0.0.0"
    port: int = 8000
    # CORS 允许来源，逗号分隔；* 表示全部（仅建议开发环境使用）
    cors_origins: str = "*"
    environment: str = "development"  # development / production

    # ========== 数据库 ==========
    # 默认存放在 backend/data/ 目录（自动创建）
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'rights_assistant.db'}"

    # ========== 上传目录 ==========
    upload_dir: str = str(BACKEND_DIR / "data" / "uploads")

    # ========== LLM 配置（OpenAI 兼容接口） ==========
    llm_model: str = "qwen-plus"
    # 快速模型（用于事实提取/法律匹配/质检等结构化步骤，显著降低耗时）
    llm_fast_model: str = "qwen-flash"
    # 是否强制每次都跑模型质检：默认 False，由规则初筛决定是否触发（省一次 10 秒级调用）
    llm_always_review: bool = False
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096

    # ========== ASR 配置 ==========
    asr_model: str = "paraformer-realtime-v2"

    # ========== 外部法律 API（预留：北大法宝等） ==========
    external_law_api_enabled: bool = False
    external_law_api_url: str = ""
    external_law_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 派生属性 ----------

    @property
    def demo_mode(self) -> bool:
        """无有效 API Key 时进入演示模式：投诉信生成走纯规则管线，不调用任何外部服务"""
        key = (self.dashscope_api_key or "").strip()
        return not key or key in ("your_dashscope_api_key_here", "sk-xxx", "sk-your-key")

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in (self.cors_origins or "").split(",") if o.strip()]
        return origins or ["*"]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
