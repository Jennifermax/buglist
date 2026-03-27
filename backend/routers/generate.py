from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from ..models.testcase import TestCase, TestCaseCreate
from ..services.ai_service import AIService

router = APIRouter(prefix="/api/testcases", tags=["generate"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def load_ai_config():
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data.get("ai", {})
    return {}

@router.post("/generate")
async def generate_testcases(document: str):
    config = load_ai_config()
    if not config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先配置 AI API")

    ai_service = AIService(
        config.get("api_url", ""),
        config.get("api_key", ""),
        config.get("model", "gpt-4o")
    )
    cases = await ai_service.generate_testcases(document)

    # 保存生成的用例
    from .testcases import load_testcases, save_testcases
    existing = load_testcases()
    new_cases = []
    for i, case_data in enumerate(cases):
        case_id = f"TC{len(existing) + i + 1:03d}"
        case = TestCase(id=case_id, **case_data)
        new_cases.append(case)
        existing.append(case)

    save_testcases(existing)
    return {"generated": len(new_cases), "cases": new_cases}
