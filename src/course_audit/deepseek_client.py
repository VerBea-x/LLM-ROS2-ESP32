"""Small OpenAI-compatible chat-completions client; secrets stay in env vars."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class MissingModelConfig(RuntimeError):
    pass


def request_options() -> dict[str, Any]:
    from urllib.parse import urlsplit
    if urlsplit(os.environ.get("LLM_BASE_URL", "")).hostname == "api.deepseek.com":
        # Temperature has no effect in thinking mode; disable it for W7's
        # temperature experiment. Explicitly freeze the bounded output budget.
        return {"thinking": {"type": "disabled"}, "max_tokens": 1024}
    return {"max_tokens": 1024}


def chat_completion(messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                    temperature: float, timeout_s: int = 45) -> dict[str, Any]:
    base_url = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    missing = [name for name, value in (("LLM_BASE_URL", base_url),
                                         ("LLM_API_KEY", api_key),
                                         ("LLM_MODEL", model)) if not value]
    if missing:
        raise MissingModelConfig("未设置环境变量：" + ", ".join(missing))
    url = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
    body = json.dumps({"model": model, "messages": messages, "tools": tools,
                       "temperature": temperature, **request_options()}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never print request headers or the API key.
        body_text = exc.read(2048).decode("utf-8", errors="replace").replace(api_key, "[REDACTED]")
        raise RuntimeError(f"模型 API 返回 HTTP {exc.code}: {body_text}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"模型 API 网络错误: {exc.reason}") from None
