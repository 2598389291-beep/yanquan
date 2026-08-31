"""LLM 客户端 — OpenAI 兼容接口（阿里云百炼 / 通义千问）

统一封装 chat 调用，供投诉生成管线各步骤使用。
演示模式（未配置 API Key）下不会调用本模块，由 demo.py 的纯规则管线接管。
"""

import json
import logging
import re
from typing import Optional

from openai import OpenAI

from ..config import settings

logger = logging.getLogger(__name__)


def _client() -> OpenAI:
    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.llm_base_url,
        timeout=60,
        max_retries=2,
    )


def chat_json(
    system_prompt: str,
    human_text: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    model: Optional[str] = None,
) -> str:
    """调用 LLM，返回原始文本内容；快速模型失败时自动回退主模型"""
    client = _client()
    chosen = model or settings.llm_model
    try:
        resp = client.chat.completions.create(
            model=chosen,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": human_text},
            ],
        )
        content = resp.choices[0].message.content or ""
        logger.info("LLM 调用完成：%s tokens=%s", chosen, resp.usage)
        return content.strip()
    except Exception as e:
        if chosen != settings.llm_model:
            logger.warning("快速模型 %s 调用失败（%s），回退 %s", chosen, e, settings.llm_model)
            resp = client.chat.completions.create(
                model=settings.llm_model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": human_text},
                ],
            )
            content = resp.choices[0].message.content or ""
            logger.info("LLM 调用完成（回退）：%s tokens=%s", settings.llm_model, resp.usage)
            return content.strip()
        raise


def extract_json(text: str):
    """从 LLM 输出中稳健提取 JSON（兼容 ```json 包裹 / 前后杂质）"""
    if not text:
        return None
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    array_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.DOTALL)
    if array_match:
        text = array_match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 最后兜底：提取最外层 { ... } 或 [ ... ]
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue
    return None


def chat_json_data(
    system_prompt: str,
    human_text: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    fallback: Optional[dict] = None,
    model: Optional[str] = None,
):
    """调用 LLM 并解析为 JSON dict；解析失败返回 fallback"""
    content = chat_json(system_prompt, human_text, temperature, max_tokens, model)
    data = extract_json(content)
    if isinstance(data, dict):
        return data
    return fallback


def chat_json_list(
    system_prompt: str,
    human_text: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    fallback: Optional[list] = None,
    model: Optional[str] = None,
):
    """调用 LLM 并解析为 JSON list；解析失败返回 fallback"""
    content = chat_json(system_prompt, human_text, temperature, max_tokens, model)
    data = extract_json(content)
    if isinstance(data, list):
        return data
    return fallback
