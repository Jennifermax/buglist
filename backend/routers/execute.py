import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.execution_service import build_step_complete_payload, run_testcase
from .browser_auth import (
    AUTH_STATE_FILE,
    get_auth_context,
    has_saved_auth_profile,
    has_saved_auth_state,
)

router = APIRouter()

connections = {}


def _normalize_runtime_error(error: Exception) -> str:
    raw_message = str(error or "").strip()
    if not raw_message:
        return "执行测试时发生未知异常"

    lowered = raw_message.lower()
    if "target page, context or browser has been closed" in lowered:
        return "执行过程中浏览器被关闭或页面上下文已失效，请重新执行一次；如果持续出现，说明当前步骤导致页面跳转或关闭后，执行器没有正确等待新页面稳定。"

    if len(raw_message) > 220:
        return raw_message[:220] + "..."

    return raw_message


def _resolve_execution_mode(execution_mode: str, *, has_live_context: bool, has_saved_state: bool, has_saved_profile: bool) -> bool:
    if execution_mode == "logged":
        return has_live_context or has_saved_state or has_saved_profile
    if execution_mode == "auto":
        return has_live_context or has_saved_state or has_saved_profile
    return False


@router.websocket("/ws/execute/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    connections[task_id] = websocket

    try:
        data = await websocket.receive_json()
        testcases = data.get("testcases", [])
        ai_config = data.get("ai_config", {})
        execution_mode = data.get("execution_mode", "auto")

        auth_context = get_auth_context()
        saved_auth_state = has_saved_auth_state()
        saved_auth_profile = has_saved_auth_profile()
        use_logged_browser = _resolve_execution_mode(
            execution_mode,
            has_live_context=auth_context is not None,
            has_saved_state=saved_auth_state,
            has_saved_profile=saved_auth_profile,
        )

        if use_logged_browser and auth_context is not None:
            AUTH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            await auth_context.storage_state(path=str(AUTH_STATE_FILE))
            saved_auth_state = True

        if execution_mode == "logged" and not use_logged_browser:
            await websocket.send_json(
                {
                    "type": "error",
                    "data": {"message": "当前选择了已登录测试，但没有可复用的登录态。请先打开专用浏览器登录并保存登录态。"},
                }
            )
            return

        if use_logged_browser and not saved_auth_state:
            await websocket.send_json(
                {
                    "type": "error",
                    "data": {"message": "检测到登录浏览器环境，但当前没有可复用的 storage state。请先在测试专用浏览器中登录并点击保存登录态。"},
                }
            )
            return

        passed = 0
        failed = 0
        total = len(testcases)
        start_time = time.time()

        for i, testcase in enumerate(testcases):
            await websocket.send_json(
                {
                    "type": "progress",
                    "data": {
                        "current_step": i + 1,
                        "total_steps": total,
                        "current_testcase": testcase.get("name", ""),
                        "status": "running",
                        "passed": passed,
                        "failed": failed,
                    },
                }
            )

            result = await asyncio.to_thread(
                run_testcase,
                testcase,
                ai_config,
                reuse_auth_state=use_logged_browser,
            )
            result["case_name"] = testcase.get("name") or result.get("case_name") or result.get("case_id")
            payload = build_step_complete_payload(result)

            if payload["result"] == "passed":
                passed += 1
            else:
                failed += 1

            await websocket.send_json({"type": "step_complete", "data": payload})

        duration = int(time.time() - start_time)
        await websocket.send_json(
            {
                "type": "all_complete",
                "data": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "duration_seconds": duration,
                },
            }
        )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "data": {"message": _normalize_runtime_error(exc)},
                }
            )
        except Exception:
            pass
    finally:
        if task_id in connections:
            del connections[task_id]
