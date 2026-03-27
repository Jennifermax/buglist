from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pathlib import Path
import json
import time

router = APIRouter()

connections = {}

@router.websocket("/ws/execute/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    connections[task_id] = websocket

    try:
        from ..services.test_runner import TestRunner
        from ..services.ai_service import AIService

        data = await websocket.receive_json()
        testcases = data.get("testcases", [])
        ai_config = data.get("ai_config", {})

        runner = TestRunner()
        ai_service = AIService(
            ai_config.get("api_url", ""),
            ai_config.get("api_key", ""),
            ai_config.get("model", "gpt-4o")
        )

        await runner.start()
        page = await runner.context.new_page()

        passed = 0
        failed = 0
        total = len(testcases)
        start_time = time.time()

        for i, tc in enumerate(testcases):
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

            # 处理视觉验证步骤
            for step_result in result.get("results", []):
                if step_result.get("needs_vision_check"):
                    vision_result = await ai_service.analyze_screenshot(
                        step_result.get("screenshot"),
                        step_result.get("description", "")
                    )
                    step_result["vision_result"] = vision_result
                    if vision_result.get("passed"):
                        passed += 1
                    else:
                        failed += 1
                elif not step_result.get("success"):
                    failed += 1

            if result.get("passed") and failed == 0:
                passed = total - failed
                if failed > 0:
                    failed -= 1

            await websocket.send_json({
                "type": "step_complete",
                "data": {
                    "testcase_id": tc.get("id"),
                    "testcase_name": tc.get("name"),
                    "result": "passed" if result.get("passed") else "failed",
                    "reason": "测试执行完成"
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
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass
    finally:
        if task_id in connections:
            del connections[task_id]
