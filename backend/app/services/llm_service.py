
"""AI LLM ?? - ???? DeepSeek / OpenAI?OpenAI ????????

???
- ??? chat() ??? chat_stream()
- ? LLM_PROVIDER ?? deepseek / openai
- ??? API Key ?? LLMNotConfiguredError????????
- ????????????????
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Dict, List

import httpx

from app.core.config import settings


class LLMNotConfiguredError(RuntimeError):
    """??? LLM API Key ??????????"""


def _provider_config():
    provider = (settings.LLM_PROVIDER or "deepseek").strip().lower()
    if provider == "deepseek":
        key = settings.DEEPSEEK_API_KEY
        base = settings.DEEPSEEK_BASE_URL
        model = settings.LLM_MODEL or "deepseek-chat"
    elif provider == "openai":
        key = settings.OPENAI_API_KEY
        base = settings.OPENAI_BASE_URL
        model = settings.LLM_MODEL or "gpt-4o-mini"
    else:
        raise LLMNotConfiguredError(f"unknown LLM provider: {provider}")
    if not key:
        raise LLMNotConfiguredError(f"LLM provider '{provider}' API key is not configured")
    return provider, key, base.rstrip("/"), model


def _chat_url(base: str) -> str:
    return f"{base}/v1/chat/completions"


def _headers(key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


class LLMService:
    """AI LLM ???"""

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """?????????????"""
        provider, key, base, model = _provider_config()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(_chat_url(base), headers=_headers(key), json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"] or ""

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """??????????????"""
        provider, key, base, model = _provider_config()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST", _chat_url(base), headers=_headers(key), json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[len("data:"):].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0]["delta"].get("content")
                    except (KeyError, IndexError, json.JSONDecodeError):
                        delta = None
                    if delta:
                        yield delta


llm_service = LLMService()
