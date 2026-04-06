from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from playwright.sync_api import Page

from .ai_backend import AIVisionBackend


@dataclass
class PageTargetToolResult:
    passed: bool
    reason: str
    confidence: float
    evidence: Dict[str, Any]


class PageTargetValidationTool:
    def __init__(self, ai_backend: AIVisionBackend):
        self.ai_backend = ai_backend

    def validate(
        self,
        page: Page,
        *,
        step_id: str,
        case_id: str,
        artifacts_dir,
        target: str,
    ) -> PageTargetToolResult:
        screenshot = artifacts_dir / f"{case_id}-{step_id}-ai.png"
        page.screenshot(path=str(screenshot))

        current_url = page.url
        try:
            current_title = page.title()
        except Exception:
            current_title = ""

        try:
            body_preview = page.locator("body").inner_text()[:1200]
        except Exception:
            body_preview = ""

        result = self.ai_backend.analyze_page_target(
            image_path=str(screenshot),
            target=target,
            current_page_url=current_url,
            current_page_title=current_title,
            body_preview=body_preview,
        )
        return PageTargetToolResult(
            passed=result.passed,
            reason=result.reason,
            confidence=result.confidence,
            evidence={
                "engine": "ai",
                "tool": "validate_page_target",
                "screenshot": str(screenshot),
                "current_url": current_url,
                "current_title": current_title,
                "body_preview": body_preview[:600],
                "confidence": result.confidence,
                "extracted_text": result.extracted_text,
                "details": result.details,
                "raw_text": result.raw_text,
            },
        )
