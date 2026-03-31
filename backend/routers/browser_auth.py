from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from playwright.async_api import BrowserContext, Error, async_playwright

from ..config import get_base_url

router = APIRouter(prefix="/api/browser-auth", tags=["browser-auth"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTH_DIR = PROJECT_ROOT / "artifacts" / "auth"
AUTH_PROFILE_DIR = AUTH_DIR / "persistent-profile"
AUTH_STATE_FILE = AUTH_DIR / "storage-state.json"

AUTH_PLAYWRIGHT = None
AUTH_CONTEXT: Optional[BrowserContext] = None
AUTH_LAST_SAVED_AT: Optional[str] = None


def _normalize_browser_error(error: Exception) -> str:
    message = str(error or "").strip()
    lowered = message.lower()
    if "target page, context or browser has been closed" in lowered or "sigtrap" in lowered:
        return "测试专用浏览器启动失败。当前环境下 Playwright 自带浏览器未能正常打开，我会优先改为调用本机已安装的 Chrome。"
    if len(message) > 260:
        return message[:260] + "..."
    return message or "测试专用浏览器启动失败"


def _build_status():
    last_updated = None
    if AUTH_STATE_FILE.exists():
        last_updated = datetime.fromtimestamp(AUTH_STATE_FILE.stat().st_mtime).isoformat()

    return {
        "browser_open": AUTH_CONTEXT is not None,
        "state_ready": AUTH_STATE_FILE.exists(),
        "last_updated": AUTH_LAST_SAVED_AT or last_updated,
        "login_url": get_base_url(),
    }


def get_auth_context() -> Optional[BrowserContext]:
    return AUTH_CONTEXT


def has_saved_auth_state() -> bool:
    return AUTH_STATE_FILE.exists()


def has_saved_auth_profile() -> bool:
    return AUTH_PROFILE_DIR.exists() and any(AUTH_PROFILE_DIR.iterdir())


@router.get("/status")
async def get_browser_auth_status():
    return _build_status()


@router.post("/open")
async def open_browser_auth_session():
    global AUTH_PLAYWRIGHT, AUTH_CONTEXT

    if AUTH_CONTEXT is not None:
        return {
            "message": "测试专用浏览器已经打开，请直接在浏览器中登录",
            **_build_status(),
        }

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        AUTH_PLAYWRIGHT = await async_playwright().start()
        AUTH_CONTEXT = await AUTH_PLAYWRIGHT.chromium.launch_persistent_context(
            user_data_dir=str(AUTH_PROFILE_DIR),
            headless=False,
            channel="chrome",
            viewport={"width": 1440, "height": 900},
        )

        page = AUTH_CONTEXT.pages[0] if AUTH_CONTEXT.pages else await AUTH_CONTEXT.new_page()
        await page.goto(get_base_url(), wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        return {
            "message": "测试专用浏览器已打开，请在该浏览器中手动完成登录，然后回到平台点击保存登录态",
            **_build_status(),
        }
    except Exception as exc:
        if AUTH_CONTEXT is not None:
            try:
                await AUTH_CONTEXT.close()
            except Exception:
                pass
        AUTH_CONTEXT = None
        if AUTH_PLAYWRIGHT is not None:
            try:
                await AUTH_PLAYWRIGHT.stop()
            except Exception:
                pass
        AUTH_PLAYWRIGHT = None
        raise HTTPException(status_code=500, detail=_normalize_browser_error(exc))


@router.post("/save")
async def save_browser_auth_state():
    global AUTH_LAST_SAVED_AT

    if AUTH_CONTEXT is None:
        raise HTTPException(status_code=400, detail="测试专用浏览器尚未打开，请先打开后再保存登录态")

    try:
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        await AUTH_CONTEXT.storage_state(path=str(AUTH_STATE_FILE))
        AUTH_LAST_SAVED_AT = datetime.now().isoformat()
        return {
            "message": "登录态已保存，后续执行测试会自动复用",
            **_build_status(),
        }
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"保存登录态失败：{exc}")


@router.post("/close")
async def close_browser_auth_session():
    global AUTH_PLAYWRIGHT, AUTH_CONTEXT

    if AUTH_CONTEXT is None:
        return {
            "message": "测试专用浏览器当前未打开",
            **_build_status(),
        }

    try:
        await AUTH_CONTEXT.storage_state(path=str(AUTH_STATE_FILE))
    except Exception:
        pass

    try:
        await AUTH_CONTEXT.close()
    except Exception:
        pass
    AUTH_CONTEXT = None

    if AUTH_PLAYWRIGHT is not None:
        try:
            await AUTH_PLAYWRIGHT.stop()
        except Exception:
            pass
    AUTH_PLAYWRIGHT = None

    return {
        "message": "测试专用浏览器已关闭",
        **_build_status(),
    }
