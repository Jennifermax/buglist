import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError

from ..models.testcase import TestCase, TestCaseBatch
from ..services.ai_service import AIService

router = APIRouter(prefix="/api/testcase-jobs", tags=["generate-jobs"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

JOBS: Dict[str, Dict[str, Any]] = {}


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


def _extract_generation_payload(payload: Any) -> Dict[str, Any]:
    document = _extract_document(payload)
    description = ""
    images = []
    source_name = ""

    if isinstance(payload, dict):
        description = str(
            payload.get("description")
            or payload.get("note")
            or payload.get("instructions")
            or ""
        ).strip()
        source_name = str(
            payload.get("source_name")
            or payload.get("document_name")
            or payload.get("file_name")
            or ""
        ).strip()
        raw_images = payload.get("images")
        if isinstance(raw_images, list):
            images = [image for image in raw_images if isinstance(image, dict)]

    return {
        "document": document,
        "description": description,
        "images": images,
        "source_name": source_name,
    }


def _append_cases(job: Dict[str, Any], cases: list):
    existing_names = {
        (str(case.get("name") or "").strip().lower(), str(case.get("expected_result") or "").strip().lower())
        for case in job["cases"]
    }

    for case in cases:
        key = (
            str(case.get("name") or "").strip().lower(),
            str(case.get("expected_result") or "").strip().lower(),
        )
        if key in existing_names:
            continue
        existing_names.add(key)
        job["cases"].append(case)


async def _run_generation_job(job_id: str, payload: Dict[str, Any]):
    job = JOBS[job_id]
    config = load_ai_config()
    ai_service = AIService(
        config.get("api_url", ""),
        config.get("api_key", ""),
        config.get("model", "gpt-5.4")
    )
    document = str(payload.get("document") or "").strip()
    description = str(payload.get("description") or "").strip()
    images = payload.get("images") or []
    source_name = str(payload.get("source_name") or "").strip()

    try:
        job["status"] = "running"

        if images:
            job["total_chunks"] = 1
            job["current_chunk"] = 1
            generated_cases = await ai_service.generate_testcases_from_multimodal(
                document_content=document,
                description=description,
                images=images,
            )
            _append_cases(job, generated_cases)
            job["generated"] = len(job["cases"])
        else:
            composed_document = document
            if description:
                composed_document = "\n\n".join(
                    part for part in [document, f"补充说明：\n{description}"] if part.strip()
                )

            chunks = ai_service.split_document_chunks(composed_document)
            job["total_chunks"] = len(chunks)

            for chunk_index, chunk in enumerate(chunks):
                job["current_chunk"] = chunk_index + 1
                chunk_cases = await ai_service.generate_testcases_for_chunk(chunk, chunk_index, len(chunks))
                _append_cases(job, chunk_cases)
                job["generated"] = len(job["cases"])

        from .testcases import load_batches, load_testcases, save_batches, save_testcases

        existing = load_testcases()
        new_cases = []
        for i, case_data in enumerate(job["cases"]):
            case_id = f"TC{len(existing) + i + 1:03d}"
            case_data["case_no"] = case_data.get("case_no") or f"{i + 1:04d}"
            try:
                case = TestCase(id=case_id, **case_data)
            except Exception:
                continue
            new_cases.append(case.model_dump())
            existing.append(case)

        save_testcases(existing)

        batch_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        batches = load_batches()
        batches.append(TestCaseBatch(
            id=batch_id,
            created_at=datetime.now().isoformat(),
            source_name=source_name or "手动输入文档",
            source_document=document,
            generated_count=len(new_cases),
            status="completed",
            cases=[TestCase(**case) for case in new_cases],
        ))
        save_batches(batches)

        job["cases"] = new_cases
        job["generated"] = len(new_cases)
        job["model"] = ai_service.active_model
        job["batch_id"] = batch_id
        job["status"] = "completed"
    except (APIConnectionError, APITimeoutError, asyncio.TimeoutError):
        job["status"] = "failed"
        job["error"] = "AI 服务连接超时或失败，请稍后重试；如果持续失败，请更换可用的 AI Base URL、API Key 或模型。"
    except APIStatusError as exc:
        job["status"] = "failed"
        detail = ""
        try:
            detail = exc.response.text
        except Exception:
            detail = ""
        if getattr(exc, "status_code", None):
            job["error"] = f"AI 服务返回异常，状态码 {exc.status_code}" + (f"：{detail}" if detail else "")
        else:
            job["error"] = "AI 服务返回异常" + (f"：{detail}" if detail else "")
    except APIError:
        job["status"] = "failed"
        job["error"] = "AI 服务调用失败，请检查当前模型、Base URL 或 API Key 是否可用"
    except Exception:
        job["status"] = "failed"
        job["error"] = "生成测试用例时发生服务端异常"


@router.post("")
async def create_generation_job(payload: Any = Body(...)):
    generation_payload = _extract_generation_payload(payload)
    if not generation_payload["document"] and not generation_payload["description"] and not generation_payload["images"]:
        raise HTTPException(status_code=400, detail="请先提供产品文档内容、说明或图片")

    config = load_ai_config()
    if not config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先配置 AI API")

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "current_chunk": 0,
        "total_chunks": 0,
        "generated": 0,
        "batch_id": "",
        "cases": [],
        "error": "",
        "model": config.get("model", "gpt-5.4"),
    }
    asyncio.create_task(_run_generation_job(job_id, generation_payload))
    return JOBS[job_id]


@router.get("/{job_id}")
async def get_generation_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
