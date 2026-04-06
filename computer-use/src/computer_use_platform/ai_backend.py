from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import requests

from .config import RuntimeConfig


@dataclass
class AIAnalysisResult:
    passed: bool
    confidence: float
    reason: str
    extracted_text: str
    details: Dict[str, Any]
    raw_text: str


@dataclass
class AIElementSelectionResult:
    candidate_id: str
    confidence: float
    reason: str
    details: Dict[str, Any]
    raw_text: str


@dataclass
class AIStepNormalizationResult:
    parsed_step: Dict[str, Any]
    confidence: float
    reason: str
    raw_text: str


class AIVisionBackend:
    def __init__(self, config: RuntimeConfig):
        self.config = config

    def analyze(self, image_path: str, target: str, instruction: str) -> AIAnalysisResult:
        if not self.config.ai_enabled:
            raise RuntimeError("AI backend is not configured")

        prompt = (
            "你是软件测试平台的视觉断言引擎。"
            "请根据截图判断指定目标是否满足。"
            "必须返回 JSON，不要返回 markdown。"
            'JSON 格式为 {"passed": boolean, "confidence": number, "reason": string, "extracted_text": string, "details": object}。'
            f" 当前验证目标: {target}。"
            f" 验证要求: {instruction}。"
            " 如果截图无法支持结论，请 passed=false，并说明原因。"
        )
        payload = {
            "model": self.config.ai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": self._image_data_url(image_path),
                            },
                        },
                    ],
                }
            ],
        }
        response = requests.post(
            f"{self.config.ai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.ai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.config.ai_timeout,
        )
        response.raise_for_status()
        raw = response.json()
        content = self._extract_content_text(raw)
        parsed = self._parse_json(content)
        return AIAnalysisResult(
            passed=bool(parsed.get("passed", False)),
            confidence=float(parsed.get("confidence", 0)),
            reason=str(parsed.get("reason", "")).strip() or "AI 未提供原因",
            extracted_text=str(parsed.get("extracted_text", "")).strip(),
            details=parsed.get("details", {}) if isinstance(parsed.get("details", {}), dict) else {},
            raw_text=content,
        )

    def select_candidate(
        self,
        image_path: str,
        target: str,
        action: str,
        candidates: list[dict[str, Any]],
    ) -> AIElementSelectionResult:
        if not self.config.ai_enabled:
            raise RuntimeError("AI backend is not configured")

        prompt = (
            "你是软件测试平台的元素定位引擎。"
            "请结合截图和候选元素列表，为目标语句选择最匹配的一个元素。"
            "如果找不到合适元素，candidate_id 返回空字符串。"
            "必须返回 JSON，不要返回 markdown。"
            'JSON 格式为 {"candidate_id": string, "confidence": number, "reason": string, "details": object}。'
            f" 当前动作: {action}。目标语句: {target}。"
            " 候选元素列表如下：\n"
            f"{json.dumps(candidates, ensure_ascii=False, separators=(',', ':'))}"
        )
        payload = {
            "model": self.config.ai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": self._image_data_url(image_path),
                            },
                        },
                    ],
                }
            ],
        }
        response = requests.post(
            f"{self.config.ai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.ai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.config.ai_timeout,
        )
        response.raise_for_status()
        raw = response.json()
        content = self._extract_content_text(raw)
        parsed = self._parse_json(content)
        return AIElementSelectionResult(
            candidate_id=str(parsed.get("candidate_id", "")).strip(),
            confidence=float(parsed.get("confidence", 0)),
            reason=str(parsed.get("reason", "")).strip() or "AI 未提供原因",
            details=parsed.get("details", {}) if isinstance(parsed.get("details", {}), dict) else {},
            raw_text=content,
        )

    def normalize_step(self, step: Dict[str, Any], expected_result: str = "") -> AIStepNormalizationResult:
        if not self.config.ai_enabled:
            raise RuntimeError("AI backend is not configured")

        prompt = (
            "你是软件测试平台的步骤语义解析器。"
            "请把测试步骤中的自然语言转成标准 JSON，便于后续执行。"
            "必须返回 JSON，不要返回 markdown。"
            'JSON 格式为 {"action": string, "target": string, "url": string, "seconds": number, "assertion": string, "reason": string, "confidence": number, "details": object}。'
            " action 只能是: open_page, wait, click, assert。"
            " assertion 可选值包括: visible, not_visible, text_present, image_present, qr_present, background_present, code_present, unknown。"
            " 如果步骤中没有对应字段，就返回空字符串或 0。"
            " 目标是把模糊自然语言标准化，比如："
            " '点击分享弹窗右上角关闭按钮' -> target='分享弹窗右上角关闭按钮'"
            " '分享弹窗可见' -> action='assert', target='分享弹窗', assertion='visible'"
            " '分享弹窗不可见' -> action='assert', target='分享弹窗', assertion='not_visible'"
            f" 用例预期结果: {expected_result}\n"
            f" 原始步骤: {json.dumps(step, ensure_ascii=False)}"
        )
        payload = {
            "model": self.config.ai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }
        response = requests.post(
            f"{self.config.ai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.ai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.config.ai_timeout,
        )
        response.raise_for_status()
        raw = response.json()
        content = self._extract_content_text(raw)
        parsed = self._parse_json(content)
        step_data = {
            "action": str(parsed.get("action", "")).strip(),
            "target": str(parsed.get("target", "")).strip(),
            "url": str(parsed.get("url", "")).strip(),
            "seconds": parsed.get("seconds", 0) or 0,
            "assertion": str(parsed.get("assertion", "")).strip(),
            "details": parsed.get("details", {}) if isinstance(parsed.get("details", {}), dict) else {},
        }
        return AIStepNormalizationResult(
            parsed_step=step_data,
            confidence=float(parsed.get("confidence", 0)),
            reason=str(parsed.get("reason", "")).strip() or "AI 未提供原因",
            raw_text=content,
        )

    @staticmethod
    def _image_data_url(image_path: str) -> str:
        encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _extract_content_text(raw: Dict[str, Any]) -> str:
        choices = raw.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(parts)
        return str(content)

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise
