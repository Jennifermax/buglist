from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .ai_backend import AIVisionBackend


@dataclass
class TabSwitchToolResult:
    should_switch: bool
    page: Page | None
    reason: str
    confidence: float
    evidence: Dict[str, Any]


class NewTabSwitchTool:
    def __init__(self, ai_backend: AIVisionBackend):
        self.ai_backend = ai_backend

    def maybe_switch(
        self,
        page: Page,
        *,
        current_step: Dict[str, Any],
        next_step: Dict[str, Any] | None = None,
    ) -> TabSwitchToolResult:
        context = page.context
        open_pages = [item for item in context.pages if not item.is_closed()]
        page_snapshots = self._snapshot_pages(open_pages, current_page=page)

        decision = self.ai_backend.decide_tab_switch(
            current_step=current_step,
            next_step=next_step,
            current_page_url=page.url,
            current_page_title=self._safe_title(page),
            pages=page_snapshots,
        )

        selected_page = None
        if decision.should_switch:
            selected_page = self._find_page_by_index(open_pages, decision.page_index)
            if selected_page is None and decision.page_index == -1:
                open_pages = self._wait_for_new_page_candidates(context, current_page=page)
                page_snapshots = self._snapshot_pages(open_pages, current_page=page)
                evidence_pages = page_snapshots
                if len(open_pages) > 1:
                    selected_page = self._pick_new_page(open_pages, current_page=page)
            else:
                evidence_pages = page_snapshots
        else:
            evidence_pages = page_snapshots

        evidence = {
            "tool": "switch_new_tab",
            "tool_called": decision.should_switch,
            "page_snapshots": evidence_pages,
            "decision_page_index": decision.page_index,
            "confidence": decision.confidence,
            "details": decision.details,
            "raw_text": decision.raw_text,
        }

        if selected_page is None:
            return TabSwitchToolResult(
                should_switch=False,
                page=page,
                reason=decision.reason,
                confidence=decision.confidence,
                evidence=evidence,
            )

        try:
            selected_page.wait_for_load_state("domcontentloaded", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        time.sleep(1)

        evidence["selected_url"] = selected_page.url
        evidence["selected_title"] = self._safe_title(selected_page)
        return TabSwitchToolResult(
            should_switch=True,
            page=selected_page,
            reason=decision.reason,
            confidence=decision.confidence,
            evidence=evidence,
        )

    @staticmethod
    def _safe_title(page: Page) -> str:
        try:
            return page.title()
        except Exception:
            return ""

    def _snapshot_pages(self, pages: List[Page], *, current_page: Page) -> List[Dict[str, Any]]:
        snapshots: List[Dict[str, Any]] = []
        current_id = id(current_page)
        for index, candidate in enumerate(pages):
            snapshots.append(
                {
                    "page_index": index,
                    "is_current": id(candidate) == current_id,
                    "url": candidate.url,
                    "title": self._safe_title(candidate),
                }
            )
        return snapshots

    @staticmethod
    def _find_page_by_index(pages: List[Page], page_index: int) -> Page | None:
        if page_index < 0:
            return None
        for index, candidate in enumerate(pages):
            if index == page_index:
                return candidate
        return None

    @staticmethod
    def _pick_new_page(pages: List[Page], *, current_page: Page) -> Page | None:
        current_id = id(current_page)
        for candidate in pages:
            if id(candidate) != current_id and not candidate.is_closed():
                return candidate
        return None

    def _wait_for_new_page_candidates(self, context, *, current_page: Page, timeout_seconds: float = 4.0) -> List[Page]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            pages = [item for item in context.pages if not item.is_closed()]
            if len(pages) > 1 and self._pick_new_page(pages, current_page=current_page) is not None:
                return pages
            time.sleep(0.2)
        return [item for item in context.pages if not item.is_closed()]
