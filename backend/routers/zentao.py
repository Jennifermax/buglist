from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import json
from ..models.config import ZentaoConfig
from ..services.zentao_service import get_zentao_service

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
