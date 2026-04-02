from playwright.async_api import async_playwright, Page, BrowserContext
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import os
import re
from urllib.parse import urljoin
from ..config import get_base_url

class TestRunner:
    def __init__(self, *, context: BrowserContext = None, mode: str = "anonymous"):
        self.browser = None
        self.context = None
        self.playwright = None
        self.external_context = context
        self.mode = mode
        self.base_url = get_base_url()
        self.project_root = Path(__file__).resolve().parents[2]
        self.screenshot_dir = self.project_root / "artifacts" / "screenshots"
        self.auth_dir = self.project_root / "artifacts" / "auth"
        self.auth_profile_dir = self.auth_dir / "persistent-profile"
        self.auth_state_file = self.auth_dir / "storage-state.json"

    async def _launch_browser(self, *, headless: bool):
        launch_options = {"headless": headless}
        attempts = []
        chrome_binary = os.getenv("BUGLIST_CHROME_EXECUTABLE", "").strip()
        if chrome_binary:
            attempts.append({**launch_options, "executable_path": chrome_binary})
        else:
            attempts.append({**launch_options, "channel": "chrome"})
        attempts.append(launch_options)

        last_error = None
        for options in attempts:
            try:
                return await self.playwright.chromium.launch(**options)
            except Exception as exc:
                last_error = exc

        raise last_error

    async def _launch_persistent_context(self, launch_options: Dict[str, Any]):
        attempts = []
        chrome_binary = os.getenv("BUGLIST_CHROME_EXECUTABLE", "").strip()
        if chrome_binary:
            attempts.append({**launch_options, "executable_path": chrome_binary})
        else:
            attempts.append({**launch_options, "channel": "chrome"})
        attempts.append(launch_options)

        last_error = None
        for options in attempts:
            try:
                return await self.playwright.chromium.launch_persistent_context(**options)
            except Exception as exc:
                last_error = exc

        raise last_error

    def _parse_wait_ms(self, value: Any) -> int:
        if value is None:
            return 3000
        text = str(value).strip().lower()
        if not text:
            return 3000

        number_match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not number_match:
            return 3000

        amount = float(number_match.group(1))
        if "ms" in text or "毫秒" in text:
            return max(int(amount), 100)
        return max(int(amount * 1000), 300)

    def _extract_candidate_texts(self, description: str, value: Any) -> List[str]:
        raw_parts = [str(value or "").strip(), str(description or "").strip()]
        candidates: List[str] = []
        seen = set()

        for part in raw_parts:
            if not part:
                continue
            normalized = re.sub(r"[，。,：:；;（）()、]", " ", part)
            pieces = [piece.strip() for piece in normalized.split() if piece.strip()]
            for piece in [part, *pieces]:
                cleaned = piece.strip()
                if len(cleaned) < 2:
                    continue
                if cleaned in seen:
                    continue
                seen.add(cleaned)
                candidates.append(cleaned)

        return candidates

    def _expand_text_variants(self, text: str) -> List[str]:
        if not text:
            return []

        replacements = [
            ("按钮", ""),
            ("按鈕", ""),
            ("链接", ""),
            ("連結", ""),
            ("入口", ""),
            ("页面", ""),
            ("頁面", ""),
            ("跳转", ""),
            ("跳轉", ""),
            ("登录", "登入"),
            ("注册", "註冊"),
            ("报名", "報名"),
            ("参与", "參與"),
            ("验证", ""),
            ("驗證", ""),
            ("是否", ""),
            ("立即报名", "立即報名"),
            ("报名参与", "報名參與"),
        ]

        variants = {text.strip()}
        changed = True
        while changed:
            changed = False
            current = list(variants)
            for item in current:
                for old, new in replacements:
                    if old and old in item:
                        next_item = item.replace(old, new).strip()
                        if next_item and next_item not in variants:
                            variants.add(next_item)
                            changed = True

        expanded = {item for item in variants if item}
        plain = text.strip()
        if any(keyword in plain for keyword in ("报名", "報名")):
            expanded.update({"報名", "立即報名", "報名參與", "立即报名", "报名参与"})
        if any(keyword in plain for keyword in ("登录", "登入")):
            expanded.update({"登录", "登入"})
        if any(keyword in plain for keyword in ("注册", "註冊")):
            expanded.update({"注册", "註冊"})

        return [item for item in expanded if item]

    async def _click_target(self, page: Page, description: str, value: Any):
        raw_candidates = self._extract_candidate_texts(description, value)
        candidates: List[str] = []
        seen = set()

        for candidate in raw_candidates:
            for variant in self._expand_text_variants(candidate):
                if len(variant) < 2 or variant in seen:
                    continue
                seen.add(variant)
                candidates.append(variant)

        locator_candidates = []

        for text in candidates:
            locator_candidates.extend([
                page.get_by_role("button", name=re.compile(re.escape(text), re.IGNORECASE)),
                page.get_by_role("link", name=re.compile(re.escape(text), re.IGNORECASE)),
                page.get_by_text(re.compile(re.escape(text), re.IGNORECASE)),
                page.locator(f"text={text}"),
                page.locator(f'[placeholder*="{text}"]'),
                page.locator(f'[value*="{text}"]'),
                page.locator(f'[aria-label*="{text}"]'),
                page.locator(f'[title*="{text}"]'),
            ])

        for locator in locator_candidates:
            try:
                count = await locator.count()
                if count == 0:
                    continue

                for idx in range(count):
                    target = locator.nth(idx)
                    try:
                        if not await target.is_visible():
                            continue
                    except Exception:
                        continue

                    try:
                        await target.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass

                    try:
                        await target.click(timeout=3000)
                        try:
                            await page.wait_for_timeout(1200)
                        except Exception:
                            pass
                        return
                    except Exception:
                        continue
            except Exception:
                continue

        raise RuntimeError(f"未找到可点击元素：{value or description or '未知目标'}")

    async def start(self):
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        if self.external_context is not None:
            self.context = self.external_context
            return

        self.playwright = await async_playwright().start()
        if self.mode == "logged":
            context_options = {
                "viewport": {"width": 1280, "height": 720},
            }
            if self.auth_state_file.exists():
                context_options["storage_state"] = str(self.auth_state_file)
            if "storage_state" in context_options:
                self.browser = await self._launch_browser(headless=True)
                self.context = await self.browser.new_context(**context_options)
                return

            profile_has_content = self.auth_profile_dir.exists() and any(self.auth_profile_dir.iterdir())
            if profile_has_content:
                launch_options = {
                    "user_data_dir": str(self.auth_profile_dir),
                    "headless": False,
                    "viewport": {"width": 1280, "height": 720},
                }
                self.context = await self._launch_persistent_context(launch_options)
                return

        self.browser = await self._launch_browser(headless=True)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
        )

    def _build_screenshot_path(self, action: str, description: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        raw_name = f"{action}-{description}".strip("-").lower()
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in raw_name)
        safe_name = "-".join(part for part in safe_name.split("-") if part)[:80] or "step"
        return self.screenshot_dir / f"{timestamp}-{safe_name}.png"

    async def execute_step(self, page: Page, step: dict) -> dict:
        """执行单个测试步骤"""
        action = step.get("action")
        description = step.get("description", "")
        value = step.get("value", "")

        async def _save_screenshot(page_obj: Page, act: str, desc: str) -> tuple:
            """Try to save screenshot, return (screenshot_bytes, path_str_or_None)"""
            try:
                import time
                ts = time.strftime("%Y%m%d-%H%M%S-") + f"{time.time():06.0f}"[:6]
                safe = "".join(c if c.isalnum() else "-" for c in (f"{act}-{desc}").strip("-"))[:80] or "step"
                path = self.screenshot_dir / f"{ts}-{safe}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                img = await page_obj.screenshot(path=str(path))
                return img, str(path)
            except Exception:
                return None, None

        try:
            if action == "打开页面":
                target_url = value.strip() if isinstance(value, str) else ""
                if not target_url:
                    target_url = self.base_url
                elif not target_url.startswith(("http://", "https://")):
                    target_url = urljoin(f"{self.base_url}/", value.lstrip("/"))
                await page.goto(target_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                return {
                    "success": True,
                    "action": action,
                    "description": description,
                    "resolved_url": target_url
                }

            elif action == "输入":
                await page.keyboard.type(value, delay=100)
                await page.wait_for_timeout(300)
                return {"success": True, "action": action, "description": description}

            elif action == "点击":
                try:
                    await self._click_target(page, description, value)
                    return {"success": True, "action": action, "description": description}
                except RuntimeError as exc:
                    screenshot, screenshot_path = await _save_screenshot(page, action, description)
                    return {
                        "success": False,
                        "action": action,
                        "description": description,
                        "error": str(exc),
                        "screenshot": screenshot,
                        "screenshot_path": screenshot_path,
                        "needs_vision_check": screenshot is not None,
                        "vision_check_purpose": "click_failure",
                    }

            elif action == "等待":
                await page.wait_for_timeout(self._parse_wait_ms(value))
                return {"success": True, "action": action, "description": description}

            elif action == "验证":
                screenshot, screenshot_path = await _save_screenshot(page, action, description)
                return {
                    "success": True,
                    "action": action,
                    "description": description,
                    "expected_value": value,
                    "screenshot": screenshot,
                    "screenshot_path": screenshot_path,
                    "needs_vision_check": screenshot is not None
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
        import sys; sys.stderr.write(f"[DEBUG execute_testcase] START steps={len(testcase.get('steps', []))}\n"); sys.stderr.flush()
        results = []
        for step in testcase.get("steps", []):
            result = await self.execute_step(page, step)
            results.append(result)
            if not result.get("success", False):
                break

        # 判断用例整体是否通过
        all_passed = all(r.get("success", False) for r in results)
        return {
            "testcase_id": testcase.get("id"),
            "testcase_name": testcase.get("name"),
            "results": results,
            "passed": all_passed
        }

    async def cleanup(self):
        if self.external_context is not None:
            return

        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
