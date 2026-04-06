from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass
class SessionState:
    current_url: str = ""
    clicked_targets: list[str] = field(default_factory=list)
    last_scope: str = "viewport"


class MockComputerUseBackend:
    def __init__(self, mock_context: Dict[str, Any]):
        self.mock_context = mock_context
        self.state = SessionState()

    def open_page(self, url: str) -> Tuple[bool, str, Dict[str, Any]]:
        self.state.current_url = url
        return True, "页面已打开", {"url": url}

    def wait(self, seconds: int) -> Tuple[bool, str, Dict[str, Any]]:
        return True, f"已等待 {seconds} 秒", {"seconds": seconds}

    def click(self, target: str) -> Tuple[bool, str, Dict[str, Any]]:
        if target not in self.mock_context.get("clickable_targets", []):
            return False, f"未找到可点击目标: {target}", {"target": target}
        self.state.clicked_targets.append(target)
        return True, f"已点击 {target}", {"target": target}


class MockVisionBackend:
    def __init__(self, mock_context: Dict[str, Any]):
        self.mock_context = mock_context

    def object_visible(self, target: str, scope: str) -> Tuple[bool, str, Dict[str, Any]]:
        visible_targets = set(self.mock_context.get("vision_targets", []))
        if target in visible_targets:
            return True, f"已识别到 {target}", {"target": target, "scope": scope}
        return False, f"未识别到 {target}", {"target": target, "scope": scope}


class MockOCRBackend:
    def __init__(self, mock_context: Dict[str, Any]):
        self.mock_context = mock_context

    def text_contains(self, scope: str, keywords: list[str], target: str) -> Tuple[bool, str, Dict[str, Any]]:
        text = self._text_for_scope(scope)
        missing = [keyword for keyword in keywords if keyword not in text]
        if not missing:
            return True, f"已识别到 {target} 相关文本", {"scope": scope, "text": text}
        return False, f"缺少关键词: {', '.join(missing)}", {"scope": scope, "text": text}

    def pattern_match(self, scope: str, pattern: str, target: str) -> Tuple[bool, str, Dict[str, Any]]:
        text = self._text_for_scope(scope)
        matched = re.search(pattern, text)
        if matched:
            return True, f"已识别到 {target}", {"scope": scope, "text": text, "match": matched.group(0)}
        return False, f"未匹配到 {target}", {"scope": scope, "text": text, "pattern": pattern}

    def _text_for_scope(self, scope: str) -> str:
        mapping = self.mock_context.get("ocr_text_by_scope", {})
        return mapping.get(scope, "")
