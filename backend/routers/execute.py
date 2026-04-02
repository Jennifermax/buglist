from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pathlib import Path
import time

router = APIRouter()

connections = {}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    runner = None

    try:
        from ..services.test_runner import TestRunner
        from ..services.ai_service import AIService
        from .browser_auth import get_auth_context, has_saved_auth_profile, has_saved_auth_state

        data = await websocket.receive_json()
        testcases = data.get("testcases", [])
        ai_config = data.get("ai_config", {})
        execution_mode = data.get("execution_mode", "auto")

        import sys; sys.stderr.write(f"[DEBUG WS] received testcases={len(testcases)}, ai_config_keys={list(ai_config.keys())}\n"); sys.stderr.flush()

        auth_context = get_auth_context()
        saved_auth_state = has_saved_auth_state()
        saved_auth_profile = has_saved_auth_profile()
        use_logged_browser = _resolve_execution_mode(
            execution_mode,
            has_live_context=auth_context is not None,
            has_saved_state=saved_auth_state,
            has_saved_profile=saved_auth_profile,
        )

        if execution_mode == "logged" and not use_logged_browser:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "当前选择了已登录测试，但没有可复用的登录态。请先打开专用浏览器登录并保存登录态。"}
            })
            return

        runner = TestRunner(
            context=auth_context if use_logged_browser else None,
            mode="logged" if use_logged_browser else "anonymous",
        )
        ai_service = None

        try:
            await runner.start()
            import sys; sys.stderr.write(f"[DEBUG] runner.start() OK\n"); sys.stderr.flush()
        except Exception as e:
            import sys; sys.stderr.write(f"[DEBUG] runner.start() error: {e}\n"); sys.stderr.flush()

        try:
            if use_logged_browser:
                page = runner.context.pages[0] if runner.context.pages else await runner.context.new_page()
            else:
                page = await runner.context.new_page()
            import sys; sys.stderr.write(f"[DEBUG] new_page() OK\n"); sys.stderr.flush()
        except Exception as e:
            import sys; sys.stderr.write(f"[DEBUG] new_page() error: {e}\n"); sys.stderr.flush()
            await websocket.send_json({"type": "error", "data": {"message": f"浏览器创建失败: {e}"}})
            return

        passed = 0
        failed = 0
        total = len(testcases)
        start_time = time.time()

        for i, tc in enumerate(testcases):
            import sys; sys.stderr.write(f"[DEBUG] execute_testcase loop i={i} tc={tc.get('name','?')[:30]}\n"); sys.stderr.flush()
            await websocket.send_json({
                "type": "progress",
                "data": {
                    "current_step": i + 1,
                    "total_steps": total,
                    "current_testcase": tc.get("name", ""),
                    "status": "running",
                    "passed": passed,
                    "failed": failed
                }
            })

            result = await runner.execute_testcase(page, tc)
            testcase_failed = False
            testcase_reason = "测试执行完成"
            vision_details = []
            screenshots = []

            # 处理视觉验证步骤
            for step_result in result.get("results", []):
                screenshot_path = step_result.get("screenshot_path")
                if screenshot_path:
                    try:
                        relative_path = Path(screenshot_path).resolve().relative_to(PROJECT_ROOT)
                        screenshots.append({
                            "name": Path(screenshot_path).name,
                            "url": f"/{relative_path.as_posix()}",
                            "description": step_result.get("description", ""),
                            "action": step_result.get("action", ""),
                        })
                    except Exception:
                        pass

                if step_result.get("needs_vision_check"):
                    if ai_service is None:
                        ai_service = AIService(
                            ai_config.get("api_url", ""),
                            ai_config.get("api_key", ""),
                            ai_config.get("model", "gpt-5.4")
                        )
                    try:
                        vision_result = await ai_service.analyze_screenshot(
                            step_result.get("screenshot"),
                            step_result.get("description", ""),
                            expected_value=step_result.get("expected_value", ""),
                            purpose=step_result.get("vision_check_purpose", "validation"),
                        )
                    except Exception as vision_exc:
                        import sys; sys.stderr.write(f"[DEBUG] vision analysis error: {vision_exc}\n"); sys.stderr.flush()
                        vision_result = {"passed": False, "reason": f"视觉分析请求失败: {str(vision_exc)[:200]}"}
                    step_result["vision_result"] = vision_result
                    vision_details.append(vision_result)
                    if not vision_result.get("passed"):
                        testcase_failed = True
                        testcase_reason = vision_result.get("reason", "AI 视觉校验未通过")
                elif not step_result.get("success"):
                    testcase_failed = True
                    testcase_reason = step_result.get("error", "测试步骤执行失败")

            testcase_result = "failed" if testcase_failed else "passed"
            if testcase_failed:
                failed += 1
            else:
                passed += 1

            await websocket.send_json({
                "type": "step_complete",
                "data": {
                    "testcase_id": tc.get("id"),
                    "testcase_name": tc.get("name"),
                    "result": testcase_result,
                    "reason": testcase_reason,
                    "vision_details": vision_details,
                    "screenshots": screenshots,
                }
            })

        await runner.cleanup()
        duration = int(time.time() - start_time)

        await websocket.send_json({
            "type": "all_complete",
            "data": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "duration_seconds": duration
            }
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import sys; sys.stderr.write(f"[DEBUG] Exception in WS: {type(e).__name__}: {e}\n"); sys.stderr.flush()
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": _normalize_runtime_error(e)}
            })
        except:
            pass
    finally:
        try:
            await runner.cleanup()
        except Exception:
            pass
        if task_id in connections:
            del connections[task_id]
