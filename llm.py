"""共享 LLM 客户端：统一加载 .env，带超时与自动重试。

所有 Agent 都通过 chat_completion() 调用大模型，避免各自重复初始化
OpenAI 客户端，并统一处理网络抖动导致的一次性失败。
"""
import os
import threading
import time
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

if not all([LLM_API_KEY, LLM_BASE_URL, LLM_MODEL]):
    raise RuntimeError(
        "缺少 LLM 配置：请在 .env 中设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL"
    )

# 默认超时 120 秒；可用 .env 里的 LLM_TIMEOUT 覆盖
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    timeout=LLM_TIMEOUT,
)

# 价格（人民币 / 百万 token），可在 .env 覆盖，用于估算成本
INPUT_PRICE_PER_M = float(os.getenv("LLM_INPUT_PRICE_PER_M", "2"))
OUTPUT_PRICE_PER_M = float(os.getenv("LLM_OUTPUT_PRICE_PER_M", "8"))

# 每个线程独立累计 token 用量（研究任务在后台线程运行）
_local = threading.local()


def _ensure_local() -> None:
    if not hasattr(_local, "total_tokens"):
        _local.prompt_tokens = 0
        _local.completion_tokens = 0
        _local.total_tokens = 0


def reset_usage() -> None:
    _local.prompt_tokens = 0
    _local.completion_tokens = 0
    _local.total_tokens = 0


def get_usage() -> Dict[str, int]:
    _ensure_local()
    return {
        "prompt_tokens": _local.prompt_tokens,
        "completion_tokens": _local.completion_tokens,
        "total_tokens": _local.total_tokens,
    }


def estimate_cost(usage: Dict[str, int]) -> float:
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    return (prompt / 1_000_000 * INPUT_PRICE_PER_M) + (
        completion / 1_000_000 * OUTPUT_PRICE_PER_M
    )


def _record_usage(response) -> None:
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        _ensure_local()
        _local.prompt_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        _local.completion_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
        _local.total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
    except Exception:
        pass


def chat_completion(
    messages,
    temperature=0.1,
    max_tokens=None,
    max_retries=3,
    retry_delay=2.0,
):
    """调用 LLM，带超时与重试；返回去除首尾空白的文本内容。"""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            kwargs = {
                "model": LLM_MODEL,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            response = client.chat.completions.create(**kwargs)
            _record_usage(response)
            content = response.choices[0].message.content
            return (content or "").strip()
        except Exception as e:
            last_error = e
            if attempt >= max_retries:
                break
            print(
                f"[llm] 调用失败（{attempt}/{max_retries}）："
                f"{type(e).__name__}: {e}，{retry_delay}s 后重试..."
            )
            time.sleep(retry_delay)
    raise RuntimeError(
        f"LLM 调用失败（已重试 {max_retries} 次）：{last_error}"
    )
