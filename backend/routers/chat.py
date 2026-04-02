import asyncio
from typing import Any, List

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
import json
import httpx
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError
from ..services.ai_service import _chat_completions_url, _normalize_openai_base_url, _openai_compatible_headers

router = APIRouter(prefix="/api/chat", tags=["chat"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"
CHAT_TIMEOUT_SECONDS = 25


def load_ai_config():
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data.get("ai", {})
    return {}


@router.post("")
async def chat(payload: dict = Body(...)):
    messages: List[Any] = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="请先输入聊天内容")

    config = load_ai_config()
    if not config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在设置页配置 AI API")

    api_url = _normalize_openai_base_url(config.get("api_url") or "")

    async def stream():
        try:
            async with httpx.AsyncClient(timeout=CHAT_TIMEOUT_SECONDS) as client:
                response = await asyncio.wait_for(
                    client.post(
                        _chat_completions_url(api_url),
                        headers=_openai_compatible_headers(config.get("api_key", "")),
                        json={
                            "model": config.get("model", "gpt-5.4"),
                            "messages": messages,
                            "temperature": 0.7,
                        },
                    ),
                    timeout=CHAT_TIMEOUT_SECONDS,
                )
            response.raise_for_status()
            payload = response.json()
            content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "")

            if not content.strip():
                yield f"data: {json.dumps({'error': 'AI 没有返回有效内容'}, ensure_ascii=False)}\n\n"
            else:
                # 模拟流式回传，让前端现有逻辑无需大改
                for chunk in [content[i:i+80] for i in range(0, len(content), 80)]:
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)
        except (APIConnectionError, APITimeoutError, asyncio.TimeoutError):
            yield f"data: {json.dumps({'error': 'AI 聊天请求超时或连接失败，请检查当前 AI 配置'}, ensure_ascii=False)}\n\n"
        except APIStatusError as exc:
            message = "AI 服务返回异常"
            if getattr(exc, "status_code", None):
                message = f"AI 服务返回异常，状态码 {exc.status_code}"
            yield f"data: {json.dumps({'error': message}, ensure_ascii=False)}\n\n"
        except APIError:
            yield f"data: {json.dumps({'error': 'AI 服务调用失败，请检查 Base URL、API Key 或模型是否可用'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
