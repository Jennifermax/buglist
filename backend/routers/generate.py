import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pathlib import Path
import json
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError
from ..models.testcase import TestCase
from ..services.ai_service import AIService

router = APIRouter(prefix="/api/testcases", tags=["generate"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def load_ai_config():
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data.get("ai", {})
    return {}

def _extract_document(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        for key in ("document", "content", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""

@router.post("/generate")
async def generate_testcases(payload: Any = Body(...)):
    document = _extract_document(payload)
    if not document:
        raise HTTPException(status_code=400, detail="请先提供产品文档内容")

    config = load_ai_config()
    if not config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先配置 AI API")

    ai_service = AIService(
        config.get("api_url", ""),
        config.get("api_key", ""),
        config.get("model", "gpt-5.4")
    )

    try:
        cases = await ai_service.generate_testcases(document)
    except (APIConnectionError, APITimeoutError, TimeoutError, asyncio.TimeoutError):
        raise HTTPException(
            status_code=502,
            detail="AI 服务连接超时或失败，请稍后重试；如果持续失败，请更换可用的 AI Base URL、API Key 或模型。"
        )
    except APIStatusError as exc:
        detail = "AI 服务返回异常"
        if getattr(exc, "status_code", None):
            detail = f"AI 服务返回异常，状态码 {exc.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    except APIError:
        raise HTTPException(status_code=502, detail="AI 服务调用失败，请检查当前模型、Base URL 或 API Key 是否可用")
    except Exception:
        raise HTTPException(status_code=500, detail="生成测试用例时发生服务端异常")

    if not cases:
        raise HTTPException(status_code=502, detail="AI 未生成有效测试用例，请检查文档内容或当前 AI 能力")

    # 保存生成的用例
    from .testcases import load_testcases, save_testcases
    existing = load_testcases()
    new_cases = []
    for i, case_data in enumerate(cases):
        case_id = f"TC{len(existing) + i + 1:03d}"
        try:
            case = TestCase(id=case_id, **case_data)
        except Exception:
            continue
        new_cases.append(case)
        existing.append(case)

    if not new_cases:
        raise HTTPException(status_code=502, detail="AI 返回的测试用例格式不正确，无法生成表格")

    save_testcases(existing)
    return {"generated": len(new_cases), "cases": new_cases}
