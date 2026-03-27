from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from ..models.config import AppConfig, AIConfig, ZentaoConfig

router = APIRouter(prefix="/api/config", tags=["config"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def load_config() -> AppConfig:
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AppConfig(**data)
    return AppConfig()

def save_config(config: AppConfig):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(config.model_dump_json(indent=2), encoding="utf-8")

@router.get("/ai", response_model=AIConfig)
async def get_ai_config():
    return load_config().ai

@router.post("/ai")
async def save_ai_config(config: AIConfig):
    app_config = load_config()
    app_config.ai = config
    save_config(app_config)
    return {"message": "AI config saved"}

@router.get("/zentao", response_model=ZentaoConfig)
async def get_zentao_config():
    return load_config().zentao

@router.post("/zentao")
async def save_zentao_config(config: ZentaoConfig):
    app_config = load_config()
    app_config.zentao = config
    save_config(app_config)
    return {"message": "Zentao config saved"}
