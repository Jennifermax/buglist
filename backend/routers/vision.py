import base64
import json
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException
import httpx

router = APIRouter(prefix="/api/vision", tags=["vision"])

from pathlib import Path
CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"
CHAT_TIMEOUT_SECONDS = 60


def load_ai_config():
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data.get("ai", {})
    return {}


def normalize_openai_base_url(api_url: str) -> str:
    url = (api_url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url[: -len("/chat/completions")]
    if url.endswith("/v1"):
        return url
    if url.startswith("http"):
        return f"{url}/v1"
    return url


def chat_completions_url(api_url: str) -> str:
    return f"{normalize_openai_base_url(api_url)}/chat/completions"


@router.post("")
async def vision_chat(file: UploadFile = File(...)):
    """上传图片，以聊天方式获取 AI 视觉分析结果"""
    config = load_ai_config()
    api_url = normalize_openai_base_url(config.get("api_url") or "")
    api_key = config.get("api_key", "")
    model = config.get("model", "gpt-5.4")

    if not api_key:
        raise HTTPException(status_code=400, detail="请先在设置页配置 AI API")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    image_data = await file.read()
    image_base64 = base64.b64encode(image_data).decode("utf-8")

    prompt_text = "你是一个专业的图片分析助手。请仔细描述这张图片的详细内容，包括：\n1. 图片中的主要内容和场景\n2. 图片中的文字（如果有）\n3. 图片的风格、色调、氛围\n4. 任何值得注意的细节\n请用中文回答。"

    try:
        async with httpx.AsyncClient(timeout=float(CHAT_TIMEOUT_SECONDS)) as client:
            response = await asyncio.wait_for(
                client.post(
                    chat_completions_url(api_url),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                            ]
                        }]
                    },
                ),
                timeout=CHAT_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        payload = response.json()

        content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "")

        if not content.strip():
            return {"content": "AI 没有返回有效内容"}
        return {"content": content}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="AI 请求超时，请稍后重试")
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] if exc.response is not None else f"状态码: {exc.response.status_code}"
        raise HTTPException(status_code=502, detail=f"视觉 API 返回异常: {detail}")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"视觉 API 调用失败: {str(exc)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
