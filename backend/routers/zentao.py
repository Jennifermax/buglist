from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import json
from pydantic import BaseModel, Field
from ..models.config import ZentaoConfig
from ..services.zentao_service import get_zentao_service
from ..services.zentao_bug_submit_service import build_bug_payload, resolve_product_id

router = APIRouter(prefix="/api/zentao", tags=["zentao"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"ai": {}, "zentao": {}}

def save_zentao_config(config: ZentaoConfig):
    """保存禅道配置"""
    data = load_config()
    data["zentao"] = config.model_dump()
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def get_zentao_config() -> ZentaoConfig:
    config = load_config()
    zentao_data = config.get("zentao", {})
    return ZentaoConfig(**zentao_data)


class ZentaoSubmitItem(BaseModel):
    testcase_id: str = ""
    testcase_name: str = ""
    result: str = ""
    reason: str = ""
    vision_details: List[Dict[str, Any]] = Field(default_factory=list)
    screenshots: List[Dict[str, Any]] = Field(default_factory=list)


class ZentaoBatchSubmitRequest(BaseModel):
    report_items: List[ZentaoSubmitItem] = Field(default_factory=list)
    testcases: List[Dict[str, Any]] = Field(default_factory=list)
    product_id: Optional[int] = None
    module: Optional[int] = None
    assigned_to: str = ""
    opened_build: str = "trunk"
    artifact_base_url: str = ""

@router.post("/test-connection")
async def test_connection():
    """测试禅道连接"""
    config = get_zentao_config()
    if not config.url or not config.account:
        raise HTTPException(status_code=400, detail="请先配置禅道地址和账号")

    service = get_zentao_service(config)
    try:
        result = await service.test_connection()
        # 如果有密码但没有token，尝试获取token
        if not config.token and config.password:
            token_result = await service.get_token_by_password(config.password)
            if token_result.get("success"):
                config.token = token_result["token"]
                save_zentao_config(config)
                result = await service.test_connection()
        return result
    finally:
        await service.close()

@router.get("/products")
async def get_products():
    """获取产品列表"""
    config = get_zentao_config()
    if not config.url:
        raise HTTPException(status_code=400, detail="请先配置禅道地址")

    service = get_zentao_service(config)
    try:
        result = await service.get_products()
        return result
    finally:
        await service.close()

@router.get("/products/{product_id}")
async def get_product(product_id: int):
    """获取产品详情"""
    config = get_zentao_config()
    if not config.url:
        raise HTTPException(status_code=400, detail="请先配置禅道地址")

    service = get_zentao_service(config)
    try:
        result = await service.get_product(product_id)
        return result
    finally:
        await service.close()

@router.get("/products/{product_id}/modules")
async def get_product_modules(product_id: int):
    """获取产品模块"""
    config = get_zentao_config()
    if not config.url:
        raise HTTPException(status_code=400, detail="请先配置禅道地址")

    service = get_zentao_service(config)
    try:
        result = await service.get_product_modules(product_id)
        return result
    finally:
        await service.close()

@router.get("/products/{product_id}/builds")
async def get_product_builds(product_id: int):
    """获取产品版本"""
    config = get_zentao_config()
    if not config.url:
        raise HTTPException(status_code=400, detail="请先配置禅道地址")

    service = get_zentao_service(config)
    try:
        result = await service.get_product_builds(product_id)
        return result
    finally:
        await service.close()

@router.get("/bugs")
async def get_bugs(product: int = Query(None), status: str = Query(None)):
    """获取 Bug 列表"""
    config = get_zentao_config()
    if not config.url:
        raise HTTPException(status_code=400, detail="请先配置禅道地址")

    service = get_zentao_service(config)
    try:
        result = await service.get_bugs(product, status)
        return result
    finally:
        await service.close()

@router.post("/bugs")
async def create_bug(bug_data: dict):
    """创建 Bug"""
    config = get_zentao_config()
    if not config.url:
        raise HTTPException(status_code=400, detail="请先配置禅道地址")

    service = get_zentao_service(config)
    try:
        result = await service.create_bug(bug_data)
        return result
    finally:
        await service.close()


@router.post("/bugs/submit-failures")
async def submit_failed_results_to_zentao(payload: ZentaoBatchSubmitRequest):
    """将失败的自动化测试结果批量提交到禅道"""
    config = get_zentao_config()
    if not config.url or not config.account:
        raise HTTPException(status_code=400, detail="请先在设置中配置禅道账号信息")

    failed_items = [
        item.model_dump()
        for item in payload.report_items
        if str(item.result or "").lower() == "failed"
    ]
    if not failed_items:
        raise HTTPException(status_code=400, detail="没有可提交到禅道的失败用例")

    testcase_by_id = {
        str(case.get("id") or ""): case
        for case in payload.testcases
        if isinstance(case, dict)
    }

    service = get_zentao_service(config)
    try:
        if not config.token and config.password:
            token_result = await service.get_token_by_password(config.password)
            if token_result.get("success"):
                config.token = token_result["token"]
                save_zentao_config(config)
            else:
                raise HTTPException(status_code=400, detail=token_result.get("message") or "禅道 Token 获取失败")

        product_id = await resolve_product_id(service, payload.product_id)
        created: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for item in failed_items:
            testcase_id = str(item.get("testcase_id") or "")
            testcase = testcase_by_id.get(testcase_id) or {
                "id": testcase_id,
                "name": item.get("testcase_name") or testcase_id or "未命名用例",
                "priority": "P1",
                "expected_result": "",
                "steps": [],
            }
            bug_payload = build_bug_payload(
                item,
                testcase,
                product_id=product_id,
                artifact_base_url=payload.artifact_base_url,
                module=payload.module,
                assigned_to=payload.assigned_to,
                opened_build=payload.opened_build,
            )
            result = await service.create_bug(bug_payload)
            if result.get("success"):
                bug = result.get("data") or {}
                created.append(
                    {
                        "testcase_id": testcase_id,
                        "testcase_name": testcase.get("name") or item.get("testcase_name") or testcase_id,
                        "bug_id": bug.get("id"),
                        "bug_title": bug.get("title") or bug_payload["title"],
                        "product_id": product_id,
                    }
                )
            else:
                failed.append(
                    {
                        "testcase_id": testcase_id,
                        "testcase_name": testcase.get("name") or item.get("testcase_name") or testcase_id,
                        "message": result.get("message") or "创建 Bug 失败",
                        "bug_title": bug_payload["title"],
                    }
                )

        return {
            "success": len(created) > 0,
            "message": (
                f"已成功提交 {len(created)} 条失败用例到禅道"
                if not failed
                else f"部分提交成功：成功 {len(created)} 条，失败 {len(failed)} 条"
            ),
            "submitted": len(failed_items),
            "created_count": len(created),
            "failed_count": len(failed),
            "product_id": product_id,
            "created": created,
            "failed": failed,
        }
    finally:
        await service.close()

@router.get("/users")
async def get_users():
    """获取用户列表"""
    config = get_zentao_config()
    if not config.url:
        raise HTTPException(status_code=400, detail="请先配置禅道地址")

    service = get_zentao_service(config)
    try:
        result = await service.get_users()
        return result
    finally:
        await service.close()
