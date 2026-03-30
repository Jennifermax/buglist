import base64
import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI

MAX_DOCUMENT_CHARS = 12000
AI_REQUEST_TIMEOUT_SECONDS = 18
AI_REQUEST_MAX_ATTEMPTS = 1

class AIService:
    def __init__(self, api_url: str, api_key: str, model: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_url or None,
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
        self.model = model

    def _prepare_document_excerpt(self, document_content: str) -> str:
        normalized = re.sub(r"\n{3,}", "\n\n", document_content or "").strip()
        if len(normalized) <= MAX_DOCUMENT_CHARS:
            return normalized

        head_length = 9000
        tail_length = 2500
        head = normalized[:head_length].rstrip()
        tail = normalized[-tail_length:].lstrip()
        omitted = len(normalized) - head_length - tail_length
        omitted_note = f"\n\n[文档中间已省略约 {omitted} 个字符，以避免 AI 生成超时]\n\n"
        return f"{head}{omitted_note}{tail}"

    def _estimate_case_count(self, document_content: str) -> int:
        length = len(document_content.strip())
        if length >= 6000:
            return 15
        if length >= 3500:
            return 12
        if length >= 1800:
            return 10
        return 8

    def _extract_json_payload(self, content: str) -> Any:
        if not content:
            return []

        cleaned = content.strip()
        candidates = [cleaned]

        fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE)
        if fenced_match:
            candidates.append(fenced_match.group(1).strip())

        array_match = re.search(r"\[[\s\S]*\]", cleaned)
        if array_match:
            candidates.append(array_match.group(0).strip())

        object_match = re.search(r"\{[\s\S]*\}", cleaned)
        if object_match:
            candidates.append(object_match.group(0).strip())

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue

        return []

    def _coerce_cases(self, payload: Any) -> List[Any]:
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ("cases", "testcases", "items", "data", "result"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        return []

    def _normalize_action(self, raw_action: str, description: str) -> str:
        normalized_raw_action = str(raw_action or "").strip()
        direct_map = {
            "打开页面": "打开页面",
            "打开": "打开页面",
            "访问": "打开页面",
            "导航": "打开页面",
            "输入": "输入",
            "填写": "输入",
            "点击": "点击",
            "单击": "点击",
            "等待": "等待",
            "验证": "验证",
            "校验": "验证",
            "检查": "验证",
        }
        if normalized_raw_action in direct_map:
            return direct_map[normalized_raw_action]

        text = f"{normalized_raw_action} {description}".strip().lower()
        if any(keyword in text for keyword in ("等待", "sleep", "延时", "加载完成", "加载稳定")):
            return "等待"
        if any(keyword in text for keyword in ("验证", "校验", "检查", "确认", "判断", "是否", "显示", "存在")):
            return "验证"
        if any(keyword in text for keyword in ("输入", "填写", "键入", "type", "enter")):
            return "输入"
        if any(keyword in text for keyword in ("点击", "单击", "tap", "click", "提交")):
            return "点击"
        if any(keyword in text for keyword in ("打开", "访问", "进入", "跳转", "导航", "open", "url")):
            return "打开页面"
        return "验证"

    def _normalize_step(self, raw_step: Any) -> Optional[Dict[str, Any]]:
        if isinstance(raw_step, str):
            description = raw_step.strip()
            if not description:
                return None
            return {
                "action": self._normalize_action("", description),
                "description": description,
                "value": "",
            }

        if not isinstance(raw_step, dict):
            return None

        action = str(raw_step.get("action") or raw_step.get("type") or "").strip()
        description = str(
            raw_step.get("description")
            or raw_step.get("step")
            or raw_step.get("content")
            or raw_step.get("name")
            or ""
        ).strip()
        value = raw_step.get("value")
        if value is None:
            value = raw_step.get("input")
        if value is None:
            value = raw_step.get("data")
        if value is None:
            value = raw_step.get("url")

        if not description and action:
            description = action

        if not description:
            return None

        normalized_action = self._normalize_action(action, description)
        normalized_value = "" if value is None else str(value).strip()

        if normalized_action == "等待" and not normalized_value:
            normalized_value = "3"

        return {
            "action": normalized_action,
            "description": description,
            "value": normalized_value,
        }

    def _extract_document_url(self, document_content: str) -> str:
        match = re.search(r"https?://[^\s)]+", document_content)
        return match.group(0) if match else ""

    def _normalize_priority(self, raw_priority: Any) -> str:
        value = str(raw_priority or "").strip().upper()
        if value in {"P0", "P1", "P2", "P3"}:
            return value
        return "P1"

    def _derive_test_data(self, steps: List[Dict[str, Any]], raw_case: Dict[str, Any]) -> str:
        raw_value = str(
            raw_case.get("test_data")
            or raw_case.get("data")
            or raw_case.get("input_data")
            or ""
        ).strip()
        if raw_value:
            return raw_value

        inputs = []
        for step in steps:
            if step.get("action") == "输入" and step.get("value"):
                inputs.append(f"{step.get('description')}：{step.get('value')}")
        return "；".join(inputs)

    def _derive_expected_result(self, steps: List[Dict[str, Any]], raw_case: Dict[str, Any], case_name: str) -> str:
        raw_value = str(
            raw_case.get("expected_result")
            or raw_case.get("expected")
            or raw_case.get("assertion")
            or ""
        ).strip()
        if raw_value:
            return raw_value

        validations = [step.get("description", "").strip() for step in steps if step.get("action") == "验证"]
        validations = [item for item in validations if item]
        if validations:
            return "；".join(validations)

        if case_name:
            return f"{case_name}相关功能符合产品文档预期"
        return "页面与交互结果符合产品文档预期"

    def _build_fallback_steps(self, case_name: str, expected_result: str, default_url: str) -> List[Dict[str, Any]]:
        steps = []
        if default_url:
            steps.append({
                "action": "打开页面",
                "description": "打开待测页面",
                "value": default_url,
            })
        steps.append({
            "action": "等待",
            "description": "等待页面加载稳定",
            "value": "3",
        })
        steps.append({
            "action": "验证",
            "description": expected_result or f"确认 {case_name or '当前场景'} 满足预期",
            "value": "",
        })
        return steps

    def _normalize_case(self, raw_case: Any, index: int, default_url: str) -> Optional[Dict[str, Any]]:
        if isinstance(raw_case, str):
            raw_case = {"name": raw_case}

        if not isinstance(raw_case, dict):
            return None

        case_name = str(raw_case.get("name") or raw_case.get("title") or raw_case.get("scenario") or "").strip()
        raw_steps = (
            raw_case.get("steps")
            or raw_case.get("test_steps")
            or raw_case.get("procedure")
            or raw_case.get("actions")
            or []
        )

        if isinstance(raw_steps, str):
            raw_steps = [line.strip() for line in raw_steps.splitlines() if line.strip()]

        steps = []
        if isinstance(raw_steps, list):
            for step in raw_steps:
                normalized_step = self._normalize_step(step)
                if normalized_step:
                    steps.append(normalized_step)

        precondition = str(
            raw_case.get("precondition")
            or raw_case.get("preconditions")
            or raw_case.get("condition")
            or "测试环境可访问，相关账号或测试数据已准备"
        ).strip()
        expected_result = self._derive_expected_result(steps, raw_case, case_name)

        if not steps:
            steps = self._build_fallback_steps(case_name, expected_result, default_url)

        if not case_name:
            case_name = expected_result or f"文档场景用例 {index + 1}"

        return {
            "case_no": str(raw_case.get("case_no") or f"{index + 1:04d}").strip(),
            "priority": self._normalize_priority(raw_case.get("priority")),
            "name": case_name,
            "precondition": precondition,
            "test_data": self._derive_test_data(steps, raw_case),
            "expected_result": expected_result,
            "owner": str(raw_case.get("owner") or "").strip(),
            "remarks": str(raw_case.get("remarks") or raw_case.get("module") or "").strip(),
            "steps": steps,
        }

    async def generate_testcases(self, document_content: str) -> list:
        excerpt = self._prepare_document_excerpt(document_content)
        expected_count = self._estimate_case_count(excerpt)
        prompt = f"""你是一名资深测试分析师。请根据下面的产品文档，直接生成适合 Excel 表格展示的测试用例 JSON 数组。

硬性要求：
1. 至少生成 {expected_count} 条测试用例；如果文档场景较多，可以生成更多。
2. 每条测试用例必须包含以下字段：
   - case_no: 用例编号，不存在时按 0001、0002 递增
   - priority: 优先级，只能是 P0/P1/P2/P3
   - name: 用例名称
   - precondition: 前置条件
   - test_data: 测试数据
   - expected_result: 预期结果
   - owner: 负责人，没有则为空字符串
   - remarks: 备注，没有则为空字符串
   - steps: 数组，至少 3 步
3. steps 中每个步骤都必须包含：
   - action: 只能是“打开页面”“输入”“点击”“等待”“验证”之一
   - description: 步骤描述
   - value: 可为空字符串
4. 请尽量覆盖正常流程、异常流程、边界场景、页面展示与校验提示。
5. 如果文档中出现 URL，请优先把 URL 放入“打开页面”步骤的 value。
6. “等待”步骤默认使用 3 秒，适合页面加载后再截图判断。
7. 输出必须是纯 JSON 数组，不要输出 Markdown，不要输出解释文字。

产品文档：
{excerpt}"""

        last_error: Optional[Exception] = None
        for attempt in range(AI_REQUEST_MAX_ATTEMPTS):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7
                    ),
                    timeout=AI_REQUEST_TIMEOUT_SECONDS,
                )
                break
            except (APIConnectionError, APITimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt == AI_REQUEST_MAX_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(1.2 * (attempt + 1))
        else:
            raise last_error or RuntimeError("AI 请求失败")

        content = response.choices[0].message.content
        payload = self._extract_json_payload(content)
        raw_cases = self._coerce_cases(payload)
        default_url = self._extract_document_url(excerpt)

        normalized_cases = []
        for index, raw_case in enumerate(raw_cases):
            normalized_case = self._normalize_case(raw_case, index, default_url)
            if normalized_case:
                normalized_cases.append(normalized_case)

        return normalized_cases

    async def analyze_screenshot(self, image_data: bytes, description: str) -> Dict[str, Any]:
        """使用视觉模型分析截图"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        prompt = f"""请分析这张截图，判断是否符合以下预期描述：
"{description}"

请返回 JSON 格式：
{{
  "passed": true 或 false,
  "reason": "判断原因"
}}
只返回 JSON，不要返回其他内容。"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                    ]
                }
            ]
        )

        content = response.choices[0].message.content
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except:
            return {"passed": False, "reason": "解析失败"}
        return {"passed": False, "reason": "解析失败"}
