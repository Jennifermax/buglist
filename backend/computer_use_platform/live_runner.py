from __future__ import annotations

import json
import re
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
from urllib3.exceptions import NotOpenSSLWarning

from .ai_backend import AIVisionBackend
from .config import RuntimeConfig
from .element_resolver import AIElementResolver

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)


class LiveCaseRunner:
    def __init__(self, case: Dict[str, Any], artifacts_dir: str = "artifacts", runtime_config: RuntimeConfig | None = None):
        self.case = case
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[Dict[str, Any]] = []
        self.modal_ready = False
        self.config = runtime_config or RuntimeConfig.from_env()
        self.ai_backend = AIVisionBackend(self.config)
        self.element_resolver = AIElementResolver(self.ai_backend)
        self.max_attempts = 3

    def run(self) -> Dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            self.results = []
            self.modal_ready = False
            try:
                self._run_once()
                if self._should_retry_attempt(self.results) and attempt < self.max_attempts:
                    last_error = self.results[0]["reason"] if self.results else "transient browser failure"
                    continue
                last_error = ""
                break
            except Exception as exc:
                last_error = str(exc)
                self.results = [
                    {
                        "step_id": "runner",
                        "name": f"执行尝试 {attempt}",
                        "status": "fail",
                        "reason": f"运行异常: {exc}",
                        "evidence": {"attempt": attempt},
                    }
                ]
                if attempt == self.max_attempts:
                    break

        failed = [item for item in self.results if item["status"] == "fail"]
        overall = "fail" if failed else "pass"
        summary = (
            f"用例失败，失败步骤: {failed[0]['name']}，原因: {failed[0]['reason']}。"
            if failed
            else f"用例通过，共 {sum(1 for item in self.results if item['status'] == 'pass')} 个步骤通过。"
        )
        if last_error and not failed:
            summary = f"{summary} 期间发生过重试，最终已恢复。"
        return {
            "case_id": self.case["id"],
            "status": overall,
            "summary": summary,
            "runtime": {
                "ai_enabled": self.config.ai_enabled,
                "ai_provider": self.config.ai_provider,
                "ai_model": self.config.ai_model if self.config.ai_enabled else "",
                "attempts": self.max_attempts,
            },
            "steps": self.results,
        }

    def _run_once(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=self.config.headless,
                args=[
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-dev-shm-usage",
                ],
            )
            context_kwargs: Dict[str, Any] = {"viewport": {"width": 1280, "height": 720}, "locale": "zh-CN"}
            auth_state_path = Path(self.config.auth_state_path)
            if auth_state_path.exists():
                context_kwargs["storage_state"] = str(auth_state_path)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            try:
                for index, step in enumerate(self.case.get("steps", []), start=1):
                    page, status = self._run_step(page, step, index)
                    if status == "fail":
                        self._skip_following_validations(index + 1)
                        break
            finally:
                browser.close()

    @staticmethod
    def _should_retry_attempt(results: List[Dict[str, Any]]) -> bool:
        if not results:
            return True
        first_fail = next((item for item in results if item.get("status") == "fail"), None)
        if first_fail is None:
            return False
        reason = first_fail.get("reason", "")
        retry_markers = [
            "Target page, context or browser has been closed",
            "Received signal 11",
            "SIGSEGV",
        ]
        return any(marker in reason for marker in retry_markers)

    def _run_step(self, page: Page, step: Dict[str, Any], step_no: int) -> tuple[Page, str]:
        step_id = f"step-{step_no:02d}"
        semantic = self._semantic_parse_step(step)
        action = semantic["action"]
        description = semantic["description"]
        value = semantic["target"]
        semantic_evidence = semantic["evidence"]

        try:
            if action == "打开页面":
                page.goto(semantic["url"], wait_until="domcontentloaded", timeout=60000)
                evidence = {"url": page.url}
                evidence.update(semantic_evidence)
                self._record(step_id, description, "pass", "页面已打开", evidence)
                return page, "pass"

            if action == "等待":
                seconds = semantic["seconds"]
                page.wait_for_timeout(seconds * 1000)
                evidence = {"seconds": seconds}
                evidence.update(semantic_evidence)
                self._record(step_id, description, "pass", f"已等待 {seconds} 秒", evidence)
                return page, "pass"

            if action == "点击":
                resolution = self._resolve_click_target(page, value, description=description, step_id=step_id)
                locator = resolution["locator"]
                if locator is None:
                    evidence = {}
                    evidence.update(semantic_evidence)
                    evidence.update(resolution["evidence"])
                    self._record(step_id, description, "fail", f"未找到点击目标: {value}", evidence)
                    return page, "fail"
                page, click_evidence = self._click_and_switch_page(page, locator)
                if self._should_retry_social_click(value, click_evidence):
                    page, click_evidence = self._retry_click_with_alternatives(page, resolution["evidence"], click_evidence)
                evidence = {}
                evidence.update(click_evidence)
                evidence.update(semantic_evidence)
                evidence.update(resolution["evidence"])
                self._record(
                    step_id,
                    description,
                    "pass",
                    f"已点击 {value}",
                    evidence,
                )
                return page, "pass"

            if action == "验证":
                return page, self._run_validation(page, step_id, description, value, semantic_evidence)

            self._record(step_id, description, "fail", f"不支持的动作: {action}")
            return page, "fail"
        except Exception as exc:
            evidence = {}
            evidence.update(semantic_evidence)
            self._record(step_id, description, "fail", f"执行异常: {exc}", evidence)
            return page, "fail"

    def _run_validation(self, page: Page, step_id: str, description: str, value: str, semantic_evidence: Dict[str, Any]) -> str:
        normalized_value = self._normalize_validation_target(value)

        if normalized_value == "分享弹窗":
            if "/zh/login" in page.url:
                screenshot = self._save_screenshot(page, f"{self.case['id']}-{step_id}-login.png")
                self.modal_ready = False
                evidence = {
                    "current_url": page.url,
                    "screenshot": screenshot,
                    "body_preview": self._body_text(page, 600),
                }
                if self.config.ai_enabled:
                    try:
                        ai_result = self.ai_backend.analyze(
                            screenshot,
                            target="登录页",
                            instruction="判断截图是否是登录页。如果是登录页，说明未出现分享弹窗。",
                        )
                        evidence["ai"] = {
                            "confidence": ai_result.confidence,
                            "reason": ai_result.reason,
                            "extracted_text": ai_result.extracted_text,
                            "details": ai_result.details,
                        }
                    except Exception as exc:
                        evidence["ai_error"] = str(exc)
                evidence.update(semantic_evidence)
                self._record(
                    step_id,
                    description,
                    "fail",
                    "点击后跳转到登录页，未出现分享弹窗",
                    evidence,
                )
                return "fail"

            ai_result = self._try_ai_validation(
                page=page,
                step_id=step_id,
                target=value,
                instruction="判断截图中是否出现了分享弹窗或分享海报弹层。如果没有明显分享弹窗，返回 passed=false。",
            )
            if ai_result is not None:
                self.modal_ready = ai_result["status"] == "pass"
                ai_result["evidence"].update(semantic_evidence)
                self._record(step_id, description, ai_result["status"], ai_result["reason"], ai_result["evidence"])
                return ai_result["status"]

            if self._looks_like_share_modal(page):
                self.modal_ready = True
                screenshot = self._save_screenshot(page, f"{self.case['id']}-{step_id}-modal.png")
                self._record(step_id, description, "pass", "检测到分享弹窗", {"current_url": page.url, "screenshot": screenshot})
                return "pass"

            self.modal_ready = False
            screenshot = self._save_screenshot(page, f"{self.case['id']}-{step_id}-missing-modal.png")
            self._record(
                step_id,
                description,
                "fail",
                "未识别到分享弹窗",
                {"current_url": page.url, "screenshot": screenshot, "body_preview": self._body_text(page, 600)},
            )
            return "fail"

        if normalized_value == "分享弹窗不可见":
            ai_result = self._try_ai_validation(
                page=page,
                step_id=step_id,
                target=normalized_value,
                instruction="判断截图中分享弹窗是否已经关闭或不可见。如果仍然能看到分享弹窗，返回 passed=false。",
            )
            if ai_result is not None:
                self._record(step_id, description, ai_result["status"], ai_result["reason"], ai_result["evidence"])
                return ai_result["status"]

            if self._looks_like_share_modal(page):
                self._record(
                    step_id,
                    description,
                    "fail",
                    "页面中仍能识别到分享弹窗，未关闭",
                    {"engine": "rule_fallback", "body_preview": self._body_text(page, 600)},
                )
                return "fail"

            self._record(
                step_id,
                description,
                "pass",
                "未识别到分享弹窗，视为已关闭",
                {"engine": "rule_fallback", "body_preview": self._body_text(page, 600)},
            )
            return "pass"

        if normalized_value in {"Twitter页面", "Twitter相关页面", "X页面", "X/Twitter页面"}:
            return self._run_external_page_validation(page, step_id, description, normalized_value, semantic_evidence)

        if not self.modal_ready:
            self._record(step_id, description, "skipped", "前置断言失败：分享弹窗未出现")
            return "skipped"

        ai_result = self._try_ai_validation(
            page=page,
            step_id=step_id,
            target=normalized_value,
            instruction=self._instruction_for_target(normalized_value),
        )
        if ai_result is not None:
            ai_result["evidence"].update(semantic_evidence)
            self._record(step_id, description, ai_result["status"], ai_result["reason"], ai_result["evidence"])
            return ai_result["status"]

        body_text = self._body_text(page, 4000)
        if normalized_value in {"分享活动文案", "活动内容介绍", "邀请码"}:
            success, reason, evidence = self._validate_text(normalized_value, body_text)
            evidence["engine"] = "rule_fallback"
            evidence.update(semantic_evidence)
            self._record(step_id, description, "pass" if success else "fail", reason, evidence)
            return "pass" if success else "fail"

        success, reason, evidence = self._validate_visual_marker(normalized_value, page)
        evidence["engine"] = "rule_fallback"
        evidence.update(semantic_evidence)
        self._record(step_id, description, "pass" if success else "fail", reason, evidence)
        return "pass" if success else "fail"

    def _semantic_parse_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        raw_action = str(step.get("action", "")).strip()
        raw_description = str(step.get("description", "")).strip()
        raw_value = str(step.get("value", "")).strip()
        expected_result = str(self.case.get("expected_result", "")).strip()

        if self.config.ai_enabled:
            try:
                parsed = self.ai_backend.normalize_step(step=step, expected_result=expected_result)
                action_map = {
                    "open_page": "打开页面",
                    "wait": "等待",
                    "click": "点击",
                    "assert": "验证",
                }
                action = action_map.get(parsed.parsed_step.get("action", ""), raw_action)
                target = parsed.parsed_step.get("target") or raw_value
                url = parsed.parsed_step.get("url") or raw_value
                seconds = parsed.parsed_step.get("seconds") or self._parse_seconds(raw_value)
                if parsed.parsed_step.get("assertion") == "visible" and target == "分享弹窗":
                    target = "分享弹窗"
                if parsed.parsed_step.get("assertion") == "not_visible" and target == "分享弹窗":
                    target = "分享弹窗不可见"
                return {
                    "action": action or raw_action,
                    "description": raw_description or raw_action,
                    "target": target,
                    "url": url,
                    "seconds": seconds,
                    "evidence": {
                        "semantic_engine": "ai",
                        "semantic_confidence": parsed.confidence,
                        "semantic_reason": parsed.reason,
                        "semantic_raw": parsed.raw_text,
                        "semantic_parsed": parsed.parsed_step,
                    },
                }
            except Exception as exc:
                return {
                    "action": raw_action,
                    "description": raw_description,
                    "target": raw_value,
                    "url": raw_value,
                    "seconds": self._parse_seconds(raw_value),
                    "evidence": {
                        "semantic_engine": "fallback",
                        "semantic_error": str(exc),
                    },
                }

        return {
            "action": raw_action,
            "description": raw_description,
            "target": raw_value,
            "url": raw_value,
            "seconds": self._parse_seconds(raw_value),
            "evidence": {
                "semantic_engine": "fallback",
            },
        }

    def _validate_text(self, value: str, body_text: str) -> tuple[bool, str, Dict[str, Any]]:
        if value == "分享活动文案":
            keywords = ["分享", "活動"]
            missing = [kw for kw in keywords if kw not in body_text and kw.replace("活動", "活动") not in body_text]
            if missing:
                return False, f"未识别到分享活动文案关键词: {', '.join(missing)}", {"body_preview": body_text[:800]}
            return True, "已识别到分享活动文案相关文本", {"body_preview": body_text[:800]}

        if value == "活动内容介绍":
            keywords = ["活動", "活动", "介紹", "介绍"]
            if not any(keyword in body_text for keyword in keywords):
                return False, "未识别到活动内容介绍相关文本", {"body_preview": body_text[:800]}
            return True, "已识别到活动内容介绍相关文本", {"body_preview": body_text[:800]}

        if value == "邀请码":
            pattern = r"(邀請碼|邀请码)[:：]?\s*[A-Za-z0-9]{4,}"
            match = re.search(pattern, body_text)
            if not match:
                return False, "未识别到邀请码", {"body_preview": body_text[:800], "pattern": pattern}
            return True, "已识别到邀请码", {"match": match.group(0)}

        return False, f"未支持的文本验证目标: {value}", {}

    def _validate_visual_marker(self, value: str, page: Page) -> tuple[bool, str, Dict[str, Any]]:
        body_text = self._body_text(page, 4000)
        html = page.content()
        lower_html = html.lower()

        if value == "logo":
            if "bydfi" in lower_html:
                return True, "检测到页面中存在 BYDFi 标识", {"marker": "bydfi"}
            return False, "未检测到 logo 标识", {}

        if value == "分享图片":
            if "<img" in lower_html:
                return True, "检测到图片元素", {"marker": "img"}
            return False, "未检测到分享图片", {}

        if value == "二维码":
            if "qr" in lower_html or "二維碼" in body_text or "二维码" in body_text:
                return True, "检测到二维码相关标识", {"marker": "qr"}
            return False, "未检测到二维码相关标识", {}

        if value == "背景图":
            if "background" in lower_html:
                return True, "检测到背景相关样式", {"marker": "background"}
            return False, "未检测到背景图相关标识", {}

        return False, f"未支持的视觉验证目标: {value}", {}

    def _looks_like_share_modal(self, page: Page) -> bool:
        body_text = self._body_text(page, 5000)
        modal_selectors = [
            "[role='dialog']",
            ".ant-modal",
            ".modal",
            ".share-modal",
        ]
        for selector in modal_selectors:
            try:
                if page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue

        share_keywords = ["邀請碼", "邀请码", "分享", "二維碼", "二维码"]
        return sum(1 for keyword in share_keywords if keyword in body_text) >= 3

    def _resolve_click_target(self, page: Page, value: str, description: str, step_id: str) -> Dict[str, Any]:
        evidence: Dict[str, Any] = {}
        target_for_ai = self._normalize_click_target(value, description)
        if self.config.ai_enabled:
            try:
                resolved = self.element_resolver.resolve(
                    page=page,
                    target=target_for_ai,
                    action="click",
                    artifacts_dir=self.artifacts_dir,
                    artifact_prefix=f"{self.case['id']}-{step_id}",
                )
                evidence.update(resolved.evidence)
                if resolved.found:
                    locator = self.element_resolver.locator_for_candidate(page, resolved.candidate_id)
                    evidence["selected_candidate_id"] = resolved.candidate_id
                    evidence["resolver_reason"] = resolved.reason
                    return {"locator": locator, "evidence": evidence}
                evidence["resolver_reason"] = resolved.reason
            except Exception as exc:
                evidence["ai_resolver_error"] = str(exc)

        if self._normalize_click_target(value, description) == "分享图标":
            locator = page.locator("div.affix-item", has_text="分享")
            if locator.count() > 0:
                evidence["engine"] = "rule_fallback"
                evidence["resolver_reason"] = "AI 未命中，回退到 affix-item + 分享 文本"
                return {"locator": locator.first, "evidence": evidence}
            alt_locator = page.get_by_text("分享", exact=True)
            if alt_locator.count() > 0:
                evidence["engine"] = "rule_fallback"
                evidence["resolver_reason"] = "AI 未命中，回退到精确文本 分享"
                return {"locator": alt_locator.first, "evidence": evidence}

        return {"locator": None, "evidence": evidence}

    @staticmethod
    def _normalize_click_target(value: str, description: str) -> str:
        text = (description or value or "").strip()
        if "右上角" in text and ("关闭" in text or "x" in text.lower()):
            return "分享弹窗右上角关闭按钮"
        if value:
            return value
        return text

    @staticmethod
    def _normalize_validation_target(value: str) -> str:
        mapping = {
            "分享弹窗可见": "分享弹窗",
            "分享窗口可见": "分享弹窗",
            "分享弹窗不可见": "分享弹窗不可见",
            "分享窗口不可见": "分享弹窗不可见",
            "Twitter页面": "Twitter页面",
            "Twitter相关页面": "Twitter相关页面",
            "X页面": "X页面",
            "Twitter/X页面": "X/Twitter页面",
        }
        return mapping.get(value, value)

    def _skip_following_validations(self, start_step_no: int) -> None:
        remaining = self.case.get("steps", [])[start_step_no - 1 :]
        for index, step in enumerate(remaining, start=start_step_no):
            if step.get("action") == "验证":
                self._record(f"step-{index:02d}", step.get("description", ""), "skipped", "前置步骤失败，未继续执行")

    def _try_ai_validation(self, page: Page, step_id: str, target: str, instruction: str) -> Dict[str, Any] | None:
        screenshot = self._save_screenshot(page, f"{self.case['id']}-{step_id}-ai.png")
        if not self.config.ai_enabled:
            return None
        try:
            result = self.ai_backend.analyze(screenshot, target=target, instruction=instruction)
        except Exception as exc:
            return {
                "status": "fail",
                "reason": f"AI 判定异常: {exc}",
                "evidence": {"engine": "ai", "screenshot": screenshot},
            }

        return {
            "status": "pass" if result.passed else "fail",
            "reason": result.reason,
            "evidence": {
                "engine": "ai",
                "screenshot": screenshot,
                "confidence": result.confidence,
                "extracted_text": result.extracted_text,
                "details": result.details,
                "raw_text": result.raw_text,
            },
        }

    @staticmethod
    def _instruction_for_target(value: str) -> str:
        mapping = {
            "logo": "判断分享弹窗中是否存在品牌 logo 或清晰品牌标识。",
            "分享活动文案": "识别分享弹窗中的主要文案，判断是否存在分享活动文案，并尽量提取文字。",
            "分享图片": "判断分享弹窗中是否存在主要分享图片、海报或卡片图片区域。",
            "活动内容介绍": "识别截图中的活动介绍文字，判断是否存在活动内容介绍，并尽量提取文字。",
            "二维码": "判断分享弹窗中是否存在二维码。",
            "背景图": "判断分享弹窗中是否存在明显背景图或海报背景。",
            "邀请码": "识别截图中是否出现邀请码或 invite code，并尽量提取具体文字。",
            "分享弹窗不可见": "判断截图中分享弹窗是否已经关闭或不可见。如果仍能看到分享弹窗，返回 passed=false。",
            "Twitter页面": "判断当前页面是否已经跳转到 Twitter/X 相关页面。优先结合页面域名、标题、登录页、分享意图页、推文页等特征判断。",
            "Twitter相关页面": "判断当前页面是否已经跳转到 Twitter/X 相关页面。优先结合页面域名、标题、登录页、分享意图页、推文页等特征判断。",
            "X页面": "判断当前页面是否已经跳转到 X(Twitter) 相关页面。优先结合页面域名、标题、登录页、分享意图页、推文页等特征判断。",
            "X/Twitter页面": "判断当前页面是否已经跳转到 X(Twitter) 相关页面。优先结合页面域名、标题、登录页、分享意图页、推文页等特征判断。",
        }
        return mapping.get(value, f"判断截图中是否存在目标元素: {value}")

    def _record(self, step_id: str, name: str, status: str, reason: str, evidence: Dict[str, Any] | None = None) -> None:
        self.results.append(
            {
                "step_id": step_id,
                "name": name,
                "status": status,
                "reason": reason,
                "evidence": evidence or {},
            }
        )

    def _click_and_switch_page(self, page: Page, locator: Locator) -> tuple[Page, Dict[str, Any]]:
        context = page.context
        before_pages = [item for item in context.pages if not item.is_closed()]
        before_page_ids = {id(item) for item in before_pages}
        before_url = page.url

        locator.click(timeout=10000)

        new_page = self._wait_for_new_page(context, before_page_ids)
        if new_page is not None:
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=15000)
            except PlaywrightTimeoutError:
                pass
            time.sleep(1)
            return new_page, {
                "navigation": "new_page",
                "previous_url": before_url,
                "current_url": new_page.url,
                "page_count_before": len(before_pages),
                "page_count_after": len([item for item in context.pages if not item.is_closed()]),
            }

        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except PlaywrightTimeoutError:
            pass
        time.sleep(2)
        return page, {
            "navigation": "same_page",
            "previous_url": before_url,
            "current_url": page.url,
            "page_count_before": len(before_pages),
            "page_count_after": len([item for item in context.pages if not item.is_closed()]),
        }

    def _retry_click_with_alternatives(
        self,
        page: Page,
        resolution_evidence: Dict[str, Any],
        initial_evidence: Dict[str, Any],
    ) -> tuple[Page, Dict[str, Any]]:
        alternative_ids = self._extract_alternative_candidate_ids(resolution_evidence)
        if not alternative_ids:
            return page, initial_evidence

        attempts = []
        for candidate_id in alternative_ids:
            locator = self.element_resolver.locator_for_candidate(page, candidate_id)
            try:
                if locator.count() <= 0:
                    attempts.append({"candidate_id": candidate_id, "result": "missing"})
                    continue
            except Exception:
                attempts.append({"candidate_id": candidate_id, "result": "lookup_failed"})
                continue

            new_page, retry_evidence = self._click_and_switch_page(page, locator)
            attempts.append(
                {
                    "candidate_id": candidate_id,
                    "navigation": retry_evidence.get("navigation"),
                    "current_url": retry_evidence.get("current_url"),
                }
            )
            if retry_evidence.get("navigation") == "new_page" or retry_evidence.get("current_url") != retry_evidence.get("previous_url"):
                retry_evidence["retry_from_alternative"] = True
                retry_evidence["retry_attempts"] = attempts
                return new_page, retry_evidence

        initial_evidence["retry_attempts"] = attempts
        return page, initial_evidence

    @staticmethod
    def _extract_alternative_candidate_ids(resolution_evidence: Dict[str, Any]) -> List[str]:
        details = resolution_evidence.get("details") or {}
        ids: List[str] = []

        alternative_candidate = details.get("alternative_candidate")
        if isinstance(alternative_candidate, str) and alternative_candidate.strip():
            ids.append(alternative_candidate.strip())

        alternative_candidates = details.get("alternative_candidates") or []
        if isinstance(alternative_candidates, list):
            for item in alternative_candidates:
                if not isinstance(item, dict):
                    continue
                candidate_id = str(item.get("candidate_id") or "").strip()
                if candidate_id:
                    ids.append(candidate_id)

        seen = set()
        unique_ids: List[str] = []
        for candidate_id in ids:
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            unique_ids.append(candidate_id)
        return unique_ids

    @staticmethod
    def _should_retry_social_click(target: str, click_evidence: Dict[str, Any]) -> bool:
        if click_evidence.get("navigation") == "new_page":
            return False
        if click_evidence.get("current_url") != click_evidence.get("previous_url"):
            return False

        normalized = (target or "").strip().lower()
        social_keywords = ("twitter", "facebook", "telegram", "whatsapp", "discord", "line", "x按钮", "x 图标", "x分享")
        return any(keyword in normalized for keyword in social_keywords)

    @staticmethod
    def _wait_for_new_page(context, before_page_ids: set[int], timeout_seconds: float = 6.0) -> Page | None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            for candidate in context.pages:
                if candidate.is_closed():
                    continue
                if id(candidate) not in before_page_ids:
                    return candidate
            time.sleep(0.2)
        return None

    def _run_external_page_validation(
        self,
        page: Page,
        step_id: str,
        description: str,
        value: str,
        semantic_evidence: Dict[str, Any],
    ) -> str:
        current_url = page.url
        try:
            current_title = page.title()
        except Exception:
            current_title = ""

        body_preview = self._body_text(page, 1200)
        screenshot = self._save_screenshot(page, f"{self.case['id']}-{step_id}-ai.png")
        evidence = {
            "current_url": current_url,
            "current_title": current_title,
            "body_preview": body_preview[:600],
            "screenshot": screenshot,
        }

        url_lower = current_url.lower()
        title_lower = current_title.lower()
        body_lower = body_preview.lower()
        twitter_text_markers = [
            "x.com",
            "twitter.com",
            "post on x",
            "share post",
            "login on x",
            "sign in to x",
            "join x",
        ]

        if any(marker in url_lower for marker in ("x.com", "twitter.com")):
            evidence.update(semantic_evidence)
            self._record(step_id, description, "pass", f"已跳转到 Twitter/X 页面: {current_url}", evidence)
            return "pass"

        if any(marker in title_lower for marker in twitter_text_markers) or any(marker in body_lower for marker in twitter_text_markers):
            evidence.update(semantic_evidence)
            self._record(step_id, description, "pass", "已识别到 Twitter/X 页面特征", evidence)
            return "pass"

        ai_result = self._try_ai_validation(
            page=page,
            step_id=step_id,
            target=value,
            instruction=self._instruction_for_target(value),
        )
        if ai_result is not None:
            ai_result["evidence"]["current_url"] = current_url
            ai_result["evidence"]["current_title"] = current_title
            ai_result["evidence"].update(semantic_evidence)
            self._record(step_id, description, ai_result["status"], ai_result["reason"], ai_result["evidence"])
            return ai_result["status"]

        evidence.update(semantic_evidence)
        self._record(step_id, description, "fail", "未识别到 Twitter/X 页面跳转结果", evidence)
        return "fail"

    def _save_screenshot(self, page: Page, filename: str) -> str:
        path = self.artifacts_dir / filename
        # Viewport screenshot is enough for step evidence and avoids crashing on very tall pages.
        page.screenshot(path=str(path))
        return str(path)

    @staticmethod
    def _parse_seconds(value: str) -> int:
        match = re.search(r"(\d+)", value)
        return int(match.group(1)) if match else 3

    @staticmethod
    def _body_text(page: Page, limit: int) -> str:
        return page.locator("body").inner_text()[:limit]


def load_live_case(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
