import base64
import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError

MAX_DOCUMENT_CHARS = 12000
AI_REQUEST_TIMEOUT_SECONDS = 25
AI_REQUEST_MAX_ATTEMPTS = 1
CHUNK_TARGET_CHARS = 1800
MAX_CHUNKS = 6


def _normalize_openai_base_url(api_url: str) -> str:
    url = (api_url or "").strip().rstrip("/")
    if not url:
        return ""
    if re.match(r"^https?://[^/]+$", url):
        return f"{url}/v1"
    return url


def _chat_completions_url(api_url: str) -> str:
    normalized = _normalize_openai_base_url(api_url)
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _openai_compatible_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "http://localhost:3000",
        "Referer": "http://localhost:3000/",
    }


class _ChatMessage:
    def __init__(self, content: str):
        self.content = content


class _ChatChoice:
    def __init__(self, content: str):
        self.message = _ChatMessage(content)


class _ChatResponse:
    def __init__(self, content: str):
        self.choices = [_ChatChoice(content)]


class AIService:
    def __init__(self, api_url: str, api_key: str, model: str):
        self.api_url = _normalize_openai_base_url(api_url)
        self.api_key = api_key
        self.model = model
        self.active_model = model

    async def _chat_create_with_fallback(self, *, messages: List[Dict[str, Any]], temperature: float):
        candidate_models = [self.active_model]

        last_error: Optional[Exception] = None
        for model_name in candidate_models:
            try:
                async with httpx.AsyncClient(timeout=AI_REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(
                        _chat_completions_url(self.api_url),
                        headers=_openai_compatible_headers(self.api_key),
                        json={
                            "model": model_name,
                            "messages": messages,
                            "temperature": temperature,
                        },
                    )
                response.raise_for_status()
                payload = response.json()
                content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
                self.active_model = model_name
                return _ChatResponse(content)
            except httpx.HTTPStatusError as exc:
                body = exc.response.text if exc.response is not None else str(exc)
                last_error = APIStatusError("AI 服务返回异常", response=exc.response, body=body)
                if "model_not_found" in body or "not available" in body:
                    continue
                raise last_error

        if last_error:
            raise last_error
        raise RuntimeError("AI 请求失败")

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

    def split_document_chunks(self, document_content: str) -> List[str]:
        normalized = re.sub(r"\n{3,}", "\n\n", document_content or "").strip()
        if not normalized:
            return []

        blocks = [block.strip() for block in re.split(r"\n{2,}", normalized) if block.strip()]
        if not blocks:
            blocks = [normalized]

        chunks: List[str] = []
        current = ""

        for block in blocks:
            if len(block) > CHUNK_TARGET_CHARS:
                pieces = [part.strip() for part in re.split(r"(?<=[。；;!?！？])", block) if part.strip()]
                if not pieces:
                    pieces = [block]
                for piece in pieces:
                    if not current:
                        current = piece
                    elif len(current) + len(piece) + 1 <= CHUNK_TARGET_CHARS:
                        current = f"{current}\n{piece}"
                    else:
                        chunks.append(current.strip())
                        current = piece
                continue

            if not current:
                current = block
            elif len(current) + len(block) + 2 <= CHUNK_TARGET_CHARS:
                current = f"{current}\n\n{block}"
            else:
                chunks.append(current.strip())
                current = block

        if current.strip():
            chunks.append(current.strip())

        return chunks[:MAX_CHUNKS]

    def _normalize_image_payloads(self, images: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
        normalized_images: List[Dict[str, str]] = []
        if not isinstance(images, list):
            return normalized_images

        for image in images:
            if not isinstance(image, dict):
                continue

            data_url = str(image.get("data_url") or "").strip()
            if data_url.startswith("data:image/"):
                normalized_images.append({
                    "name": str(image.get("name") or "").strip(),
                    "data_url": data_url,
                })
                continue

            raw_base64 = str(image.get("base64") or "").strip()
            if not raw_base64:
                continue

            mime_type = str(image.get("mime_type") or "").strip() or "image/png"
            normalized_images.append({
                "name": str(image.get("name") or "").strip(),
                "data_url": f"data:{mime_type};base64,{raw_base64}",
            })

        return normalized_images

    def _estimate_scene_count(self, document_content: str) -> int:
        text = str(document_content or "").strip()
        if not text:
            return 0

        numbered_markers = re.findall(r"(?:测试|用例|场景)\s*[：:\-]?\s*\d+", text, flags=re.IGNORECASE)
        if numbered_markers:
            return len(numbered_markers)

        line_markers = re.findall(r"(?m)^\s*(?:\d+[\.\)、]|[-*])\s+", text)
        urls = re.findall(r"https?://[^\s)]+", text)

        candidates = [
            len(urls),
            len(line_markers),
        ]
        return max(candidates) if candidates else 0

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

    def _coerce_scene_items(self, payload: Any) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        candidates = payload if isinstance(payload, list) else payload.get("scenes", []) if isinstance(payload, dict) else []
        if not isinstance(candidates, list):
            return items

        for item in candidates:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    items.append({"name": text[:40], "content": text})
                continue

            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or item.get("title") or item.get("label") or "").strip()
            content = str(item.get("content") or item.get("text") or item.get("description") or "").strip()
            if not content:
                continue
            items.append({
                "name": name or content[:40],
                "content": content,
            })

        return items

    def _fallback_split_scenes(self, document_content: str) -> List[Dict[str, str]]:
        text = str(document_content or "").strip()
        if not text:
            return []

        numbered_blocks = re.split(r"(?=(?:测试|用例|场景)\s*[：:\-]?\s*\d+)", text, flags=re.IGNORECASE)
        scenes = []
        for block in numbered_blocks:
            content = block.strip()
            if not content:
                continue
            first_line = content.splitlines()[0].strip()
            scenes.append({
                "name": first_line[:40] or f"场景 {len(scenes) + 1}",
                "content": content,
            })

        if len(scenes) > 1:
            return scenes

        return [{"name": "场景 1", "content": text}]

    async def infer_test_scenes(self, document_content: str) -> List[Dict[str, str]]:
        excerpt = self._prepare_document_excerpt(document_content)
        if not excerpt:
            return []

        prompt = f"""请阅读下面的产品文档，并判断其中包含几个独立测试场景。

要求：
1. 返回纯 JSON 数组，不要解释，不要 Markdown。
2. 每一项表示一个独立测试场景，包含：
   - name
   - content
3. 如果文档里写了“测试1、测试2、测试3”，必须拆成多个场景。
4. 如果文档里有多个不同 URL、多个不同页面、或多个明确不同的操作目标，也要拆成多个场景。
5. 不要把不同编号、不同 URL、不同活动页面合并成一个场景。
6. 如果整个文档只有一个测试目标，就只返回一个场景。

产品文档：
{excerpt}"""

        try:
            response = await self._chat_create_with_fallback(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content
            payload = self._extract_json_payload(content)
            scenes = self._coerce_scene_items(payload)
            if scenes:
                return scenes
        except Exception:
            pass

        return self._fallback_split_scenes(excerpt)

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

    def _dedupe_cases(self, cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for case in cases:
            steps = case.get("steps") or []
            open_urls = tuple(
                str(step.get("value") or "").strip().lower()
                for step in steps
                if str(step.get("action") or "").strip() == "打开页面" and str(step.get("value") or "").strip()
            )
            step_signature = tuple(
                (
                    str(step.get("action") or "").strip(),
                    str(step.get("description") or "").strip().lower(),
                    str(step.get("value") or "").strip().lower(),
                )
                for step in steps
            )
            key = (
                str(case.get("name") or "").strip().lower(),
                str(case.get("expected_result") or "").strip().lower(),
                open_urls,
                step_signature,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(case)
        return deduped

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

    def _build_chunk_generation_prompt(
        self,
        *,
        excerpt: str,
        chunk_index: int,
        total_chunks: int,
        inferred_scene_count: int,
        scene_list_text: str,
        current_scene_name: str = "",
        current_scene_content: str = "",
    ) -> str:
        scene_scope_text = ""
        if current_scene_content.strip():
            scene_scope_text = f"""
当前只允许覆盖这一个独立测试场景：
场景名称：{current_scene_name or '未命名场景'}
场景内容：
{current_scene_content}

输出要求补充：
- 这次只生成和当前场景直接相关的测试用例。
- 不要把其他场景合并进来。
- 当前场景至少输出 1 条测试用例。
"""

        return f"""你是一名测试工程师。请根据下面这部分产品文档，生成测试用例 JSON 数组。

要求：
1. 返回纯 JSON 数组，不要解释，不要 Markdown。
2. 当前是第 {chunk_index + 1}/{total_chunks} 段。AI 已识别出 {inferred_scene_count or 1} 个独立测试场景，请至少覆盖这些场景，不要合并不同场景。
3. 如果文档里明确写了“测试1、测试2”或多个独立场景，就分别输出多条测试用例。
4. 每条用例包含这些字段：
   - name
   - precondition
   - expected_result
   - steps
5. steps 是数组；每个 step 包含：
   - action: 只能是 打开页面 / 输入 / 点击 / 等待 / 验证
   - description
   - value
6. 如果这段文档里有多个不同 URL，请优先拆成不同用例，并把对应 URL 放到各自“打开页面”的 value。
7. 返回的测试用例总数不得少于 AI 识别出的独立测试场景数；如果当前只针对单个场景生成，则当前场景至少返回 1 条。
8. 只覆盖这段文档里提到的功能点、异常点和边界点。
9. 步骤和预期结果写简洁一些，方便快速返回。

AI 识别出的独立测试场景：
{scene_list_text or '未识别出明确编号场景，请根据原文自行拆分'}
{scene_scope_text}

产品文档片段：
{excerpt}"""

    async def _generate_cases_from_prompt(self, prompt: str, default_url: str) -> List[Dict[str, Any]]:
        response = await self._chat_create_with_fallback(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        content = response.choices[0].message.content
        payload = self._extract_json_payload(content)
        raw_cases = self._coerce_cases(payload)

        normalized_cases = []
        for index, raw_case in enumerate(raw_cases):
            normalized_case = self._normalize_case(raw_case, index, default_url)
            if normalized_case:
                normalized_cases.append(normalized_case)

        return normalized_cases

    async def generate_testcases_for_chunk(self, chunk_text: str, chunk_index: int = 0, total_chunks: int = 1) -> list:
        excerpt = self._prepare_document_excerpt(chunk_text)
        inferred_scenes = await self.infer_test_scenes(excerpt)
        inferred_scene_count = len(inferred_scenes)
        scene_list_text = "\n".join(
            f"{index + 1}. {scene.get('name', f'场景 {index + 1}')}\n{scene.get('content', '').strip()}"
            for index, scene in enumerate(inferred_scenes[:12])
            if str(scene.get("content") or "").strip()
        ).strip()
        scenario_hint = f"2. 当前是第 {chunk_index + 1}/{total_chunks} 段。AI 已识别出 {inferred_scene_count or 1} 个独立测试场景，请至少覆盖这些场景，不要合并不同场景。\n"
        default_url = self._extract_document_url(excerpt)
        if inferred_scene_count > 1:
            all_cases: List[Dict[str, Any]] = []
            for scene in inferred_scenes:
                scene_content = str(scene.get("content") or "").strip()
                if not scene_content:
                    continue
                scene_prompt = self._build_chunk_generation_prompt(
                    excerpt=excerpt,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    inferred_scene_count=inferred_scene_count,
                    scene_list_text=scene_list_text,
                    current_scene_name=str(scene.get("name") or "").strip(),
                    current_scene_content=scene_content,
                )
                scene_default_url = self._extract_document_url(scene_content) or default_url
                scene_cases = await self._generate_cases_from_prompt(scene_prompt, scene_default_url)
                all_cases.extend(scene_cases)
            return self._dedupe_cases(all_cases)

        prompt = self._build_chunk_generation_prompt(
            excerpt=excerpt,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            inferred_scene_count=inferred_scene_count,
            scene_list_text=scene_list_text,
        )
        return await self._generate_cases_from_prompt(prompt, default_url)

    async def generate_testcases_from_multimodal(
        self,
        *,
        document_content: str,
        description: str = "",
        images: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        excerpt = self._prepare_document_excerpt(document_content)
        normalized_images = self._normalize_image_payloads(images)
        combined_text = "\n\n".join(
            part for part in [
                f"产品文档内容：\n{excerpt}" if excerpt else "",
                f"补充说明：\n{description.strip()}" if description and description.strip() else "",
            ] if part
        ).strip()

        inferred_scenes = await self.infer_test_scenes(combined_text)
        inferred_scene_count = len(inferred_scenes)
        scene_list_text = "\n".join(
            f"{index + 1}. {scene.get('name', f'场景 {index + 1}')}\n{scene.get('content', '').strip()}"
            for index, scene in enumerate(inferred_scenes[:12])
            if str(scene.get("content") or "").strip()
        ).strip()
        scenario_hint = f"2. AI 已识别出 {inferred_scene_count or 1} 个独立测试场景，请至少覆盖这些场景，不要把不同 URL、不同编号或不同活动页面合并成一条。\n"

        instructions = f"""你是一名资深测试工程师。请根据提供的产品文档文字、补充说明以及图片内容，生成测试用例 JSON 数组。

要求：
1. 返回纯 JSON 数组，不要解释，不要 Markdown。
{scenario_hint}3. 如果文档里明确写了“测试1、测试2”或多个独立场景，就分别输出多条测试用例。
4. 每条用例包含这些字段：
   - name
   - precondition
   - expected_result
   - steps
5. steps 是数组；每个 step 包含：
   - action: 只能是 打开页面 / 输入 / 点击 / 等待 / 验证
   - description
   - value
6. 如果文字或图片里能识别到多个 URL、页面名称、按钮名称、字段名称，请尽量拆成对应的多条测试用例。
7. 返回的测试用例总数不得少于 AI 识别出的独立测试场景数。
8. 如果只有图片没有完整文字文档，也要根据图片中的界面元素和补充说明生成合理测试用例。
9. 输出内容简洁、结构稳定，方便系统直接解析。

AI 识别出的独立测试场景：
{scene_list_text or '未识别出明确编号场景，请结合原文和图片自行拆分'}
"""

        content_parts: List[Dict[str, Any]] = [{"type": "text", "text": instructions}]
        if combined_text:
            content_parts.append({"type": "text", "text": combined_text})
        for image in normalized_images[:4]:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": image["data_url"]},
            })

        response = await self._chat_create_with_fallback(
            messages=[{"role": "user", "content": content_parts}],
            temperature=0.3,
        )

        content = response.choices[0].message.content
        payload = self._extract_json_payload(content)
        raw_cases = self._coerce_cases(payload)
        default_url = self._extract_document_url(combined_text)

        normalized_cases: List[Dict[str, Any]] = []
        for index, raw_case in enumerate(raw_cases):
            normalized_case = self._normalize_case(raw_case, index, default_url)
            if normalized_case:
                normalized_cases.append(normalized_case)

        return self._dedupe_cases(normalized_cases)

    async def generate_testcases(self, document_content: str) -> list:
        chunks = self.split_document_chunks(document_content)
        if not chunks:
            return []

        all_cases: List[Dict[str, Any]] = []
        total_chunks = len(chunks)

        for chunk_index, chunk in enumerate(chunks):
            last_error: Optional[Exception] = None
            for attempt in range(AI_REQUEST_MAX_ATTEMPTS):
                try:
                    chunk_cases = await asyncio.wait_for(
                        self.generate_testcases_for_chunk(chunk, chunk_index, total_chunks),
                        timeout=AI_REQUEST_TIMEOUT_SECONDS,
                    )
                    all_cases.extend(chunk_cases)
                    break
                except (APIConnectionError, APITimeoutError, asyncio.TimeoutError) as exc:
                    last_error = exc
                    if attempt == AI_REQUEST_MAX_ATTEMPTS - 1:
                        raise
                    await asyncio.sleep(1.2 * (attempt + 1))
            else:
                raise last_error or RuntimeError("AI 请求失败")

        deduped_cases = self._dedupe_cases(all_cases)
        for index, case in enumerate(deduped_cases, start=1):
            case["case_no"] = f"{index:04d}"

        return deduped_cases

    async def analyze_screenshot(
        self,
        image_data: bytes,
        description: str,
        expected_value: str = "",
        purpose: str = "validation",
    ) -> Dict[str, Any]:
        """使用统一 AI 配置分析截图。purpose 可选: validation(默认) | click_failure"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        if not self.api_key:
            return {"passed": False, "reason": "未配置 AI API Key，请在设置页面填写统一 AI 配置"}

        if purpose == "click_failure":
            prompt = f"""观察这张网页截图：

1. 截图中的主要内容是什么？
2. 截图中是否包含「{description}」？
3. 如果不包含，页面显示的是什么？

只返回JSON格式：
{{"passed": true, "reason": "说明"}}
或
{{"passed": false, "reason": "说明"}}"""
        else:
            expected_text = (expected_value or "").strip()
            if expected_text:
                prompt = f"""你正在做严格的 UI 测试验收，请只根据截图中明确可见的内容做判断，不要猜测。

验证目标：
1. 场景描述：{description}
2. 期望看到的关键文本：{expected_text}

判定规则：
1. 只有当截图里明确可见「{expected_text}」或它的简繁体等价文本时，才能返回 passed=true。
2. 如果截图里没有明确看到该文本，哪怕有其他按钮、状态、相似区域，也必须返回 passed=false。
3. 不允许因为“页面上有按钮”或“看起来像正确区域”而判定通过。
4. reason 要明确说明截图里实际看到了什么文本，是否看到目标文本。

只返回JSON格式：
{{"passed": true, "reason": "说明"}}
或
{{"passed": false, "reason": "说明"}}"""
            else:
                prompt = f"""你正在做严格的 UI 测试验收，请只根据截图中明确可见的内容做判断，不要猜测。

验证目标：{description}

如果截图中没有足够证据证明该描述成立，就返回 passed=false。

只返回JSON格式：
{{"passed": true, "reason": "说明"}}
或
{{"passed": false, "reason": "说明"}}"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _chat_completions_url(self.api_url),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.active_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                                ],
                            }
                        ],
                        "temperature": 0.0,
                    },
                )
            response.raise_for_status()
            payload = response.json()
        except Exception as api_exc:
            return {"passed": False, "reason": f"视觉模型请求失败: {str(api_exc)[:200]}"}

        content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        try:
            # 找最后一个 { 和最后一个 }，避免被模型的思考过程干扰
            last_brace = content.rfind('}')
            if last_brace < 0:
                return {"passed": False, "reason": "解析失败: 响应中无 JSON"}
            search_start = max(0, last_brace - 2000)
            first_brace = content.find('{', search_start)
            if first_brace < 0:
                return {"passed": False, "reason": "解析失败: 响应中无 JSON 开头"}
            json_str = content[first_brace:last_brace + 1]
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            return {"passed": False, "reason": f"解析失败: {e}"}
        except Exception:
            return {"passed": False, "reason": "解析失败"}
