from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, List, Optional

from .zentao_service import ZentaoService


def _priority_to_zentao(priority: str) -> int:
    normalized = str(priority or "").strip().upper()
    mapping = {
        "P0": 1,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4,
    }
    return mapping.get(normalized, 3)


def _stringify(value: Any) -> str:
    return str(value or "").strip()


def _build_step_lines(steps: List[Dict[str, Any]]) -> str:
    if not steps:
        return "未提供原始测试步骤"

    lines: List[str] = []
    for index, step in enumerate(steps, start=1):
        action = _stringify(step.get("action"))
        description = _stringify(step.get("description"))
        value = _stringify(step.get("value"))
        parts = [part for part in [action, description] if part]
        line = " ".join(parts) or f"步骤 {index}"
        if value:
            line = f"{line}：{value}"
        lines.append(f"{index}. {line}")
    return "\n".join(lines)


def _build_ai_reason(vision_details: List[Dict[str, Any]]) -> str:
    reasons = [
        _stringify(item.get("reason"))
        for item in vision_details or []
        if _stringify(item.get("reason"))
    ]
    if not reasons:
        return "无"
    return "\n".join(f"- {reason}" for reason in reasons)


def _resolve_screenshot_absolute_url(raw_url: str, artifact_base_url: str) -> str:
    raw = _stringify(raw_url)
    normalized_base = _stringify(artifact_base_url).rstrip("/")
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("/") and normalized_base:
        return f"{normalized_base}{raw}"
    return raw


def _build_screenshot_lines(screenshots: List[Dict[str, Any]], artifact_base_url: str) -> str:
    if not screenshots:
        return "无"

    normalized_base = _stringify(artifact_base_url).rstrip("/")
    lines: List[str] = []
    for shot in screenshots:
        raw_url = _stringify(shot.get("url"))
        label = _stringify(shot.get("description")) or _stringify(shot.get("name")) or "执行截图"
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            resolved_url = raw_url
        elif raw_url.startswith("/") and normalized_base:
            resolved_url = f"{normalized_base}{raw_url}"
        else:
            resolved_url = raw_url or "无可访问地址"
        lines.append(f"- {label}：{resolved_url}")
    return "\n".join(lines)


def _build_screenshot_html_embeds(screenshots: List[Dict[str, Any]], artifact_base_url: str) -> str:
    """禅道部分版本步骤支持 HTML；附件接口失败时仍可在正文中显示外链图片。"""
    if not screenshots:
        return ""
    blocks: List[str] = []
    for shot in screenshots:
        raw_url = _stringify(shot.get("url"))
        abs_url = _resolve_screenshot_absolute_url(raw_url, artifact_base_url)
        if not abs_url.startswith(("http://", "https://")):
            continue
        label = _stringify(shot.get("description")) or _stringify(shot.get("name")) or "执行截图"
        safe_label = html.escape(label, quote=True)
        safe_src = html.escape(abs_url, quote=True)
        blocks.append(
            f'<p><strong>{safe_label}</strong><br/>'
            f'<img src="{safe_src}" alt="{safe_label}" style="max-width:min(960px,100%);height:auto;border:1px solid #ddd"/></p>'
        )
    if not blocks:
        return ""
    return (
        "\n---\n截图预览（HTML，若禅道将步骤按富文本渲染则可直接显示图片；"
        "若仅显示为代码，请以附件或下方链接为准）：\n"
        + "\n".join(blocks)
    )


def build_bug_payload(
    report_item: Dict[str, Any],
    testcase: Dict[str, Any],
    *,
    product_id: int,
    artifact_base_url: str = "",
    module: Optional[int] = None,
    assigned_to: str = "",
    opened_build: str = "trunk",
) -> Dict[str, Any]:
    testcase_id = _stringify(testcase.get("id") or report_item.get("testcase_id"))
    testcase_name = _stringify(testcase.get("name") or report_item.get("testcase_name")) or "未命名用例"
    priority = _stringify(testcase.get("priority")) or "P1"
    case_no = _stringify(testcase.get("case_no"))
    failed_reason = _stringify(report_item.get("reason")) or "自动化执行失败"
    expected_result = _stringify(testcase.get("expected_result")) or "与测试用例预期一致"
    precondition = _stringify(testcase.get("precondition")) or "无"
    test_data = _stringify(testcase.get("test_data")) or "无"
    ai_reason = _build_ai_reason(report_item.get("vision_details") or [])
    screenshot_lines = _build_screenshot_lines(report_item.get("screenshots") or [], artifact_base_url)
    screenshot_html = _build_screenshot_html_embeds(report_item.get("screenshots") or [], artifact_base_url)
    step_lines = _build_step_lines(testcase.get("steps") or [])

    title_parts = ["[Buglist自动提单]"]
    if priority:
        title_parts.append(f"[{priority}]")
    if testcase_id:
        title_parts.append(f"[{testcase_id}]")
    title = "".join(title_parts) + testcase_name

    body_parts = [
        f"来源：Buglist 自动化测试平台",
        f"提交时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"用例ID：{testcase_id or '无'}",
        f"用例编号：{case_no or '无'}",
        f"用例名称：{testcase_name}",
        f"前置条件：{precondition}",
        f"测试数据：{test_data}",
        "",
        "测试步骤：",
        step_lines,
        "",
        f"预期结果：{expected_result}",
        "",
        f"实际结果：{failed_reason}",
        "",
        "AI 判定说明：",
        ai_reason,
        "",
        "关键截图：",
        screenshot_lines,
    ]
    if screenshot_html:
        body_parts.append(screenshot_html)
    steps = "\n".join(body_parts)

    payload: Dict[str, Any] = {
        "product": product_id,
        "title": title,
        "pri": _priority_to_zentao(priority),
        "severity": _priority_to_zentao(priority),
        "type": "codeerror",
        "openedBuild": opened_build or "trunk",
        "steps": steps,
        "expectedResult": expected_result,
        "browser": "Chrome",
        "os": "macOS",
    }

    if module is not None:
        payload["module"] = module
    if assigned_to:
        payload["assignedTo"] = assigned_to
    return payload


async def resolve_product_id(service: ZentaoService, preferred_product_id: Optional[int] = None) -> int:
    if preferred_product_id:
        return int(preferred_product_id)

    result = await service.get_products()
    if result.get("success"):
        for product in result.get("data") or []:
            if isinstance(product, dict) and product.get("id"):
                return int(product["id"])

    return 1
