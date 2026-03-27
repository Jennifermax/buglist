from playwright.async_api import async_playwright, Page, BrowserContext
from typing import List, Dict, Any
import asyncio

class TestRunner:
    def __init__(self):
        self.browser = None
        self.context = None
        self.playwright = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )

    async def execute_step(self, page: Page, step: dict) -> dict:
        """执行单个测试步骤"""
        action = step.get("action")
        description = step.get("description", "")
        value = step.get("value", "")

        try:
            if action == "打开页面":
                await page.goto(value, wait_until="domcontentloaded")
                await page.wait_for_timeout(1000)
                return {"success": True, "action": action, "description": description}

            elif action == "输入":
                await page.keyboard.type(value, delay=100)
                await page.wait_for_timeout(300)
                return {"success": True, "action": action, "description": description}

            elif action == "点击":
                # 点击页面中心作为简化实现
                await page.mouse.click(500, 300)
                await page.wait_for_timeout(300)
                return {"success": True, "action": action, "description": description}

            elif action == "等待":
                await page.wait_for_timeout(float(value) * 1000)
                return {"success": True, "action": action, "description": description}

            elif action == "验证":
                # 截图并返回用于 AI 分析
                screenshot = await page.screenshot()
                return {
                    "success": True,
                    "action": action,
                    "description": description,
                    "screenshot": screenshot,
                    "needs_vision_check": True
                }

        except Exception as e:
            return {
                "success": False,
                "action": action,
                "description": description,
                "error": str(e)
            }

    async def execute_testcase(self, page: Page, testcase: dict) -> dict:
        """执行单个测试用例的所有步骤"""
        results = []
        for step in testcase.get("steps", []):
            result = await self.execute_step(page, step)
            results.append(result)

        # 判断用例整体是否通过
        all_passed = all(r.get("success", False) for r in results)
        return {
            "testcase_id": testcase.get("id"),
            "testcase_name": testcase.get("name"),
            "results": results,
            "passed": all_passed
        }

    async def cleanup(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
