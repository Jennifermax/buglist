from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .backends import MockComputerUseBackend, MockOCRBackend, MockVisionBackend
from .models import Case, CaseResult, Step, StepResult


def load_case(path: str) -> Case:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    steps = [
        Step(
            id=item["id"],
            kind=item["kind"],
            engine=item["engine"],
            name=item["name"],
            required=item.get("required", True),
            input=item.get("input", {}),
            action=item.get("action"),
            assertion=item.get("assertion"),
        )
        for item in raw["steps"]
    ]
    return Case(
        meta=raw["meta"],
        runtime=raw.get("runtime", {}),
        steps=steps,
        mock_context=raw.get("mock_context", {}),
    )


class CaseRunner:
    def __init__(self, case: Case):
        self.case = case
        self.computer_use = MockComputerUseBackend(case.mock_context)
        self.vision = MockVisionBackend(case.mock_context)
        self.ocr = MockOCRBackend(case.mock_context)

    def run(self) -> CaseResult:
        step_results: List[StepResult] = []
        stop_on_failure = self.case.runtime.get("stop_on_failure", True)

        for step in self.case.steps:
            result = self._run_step(step)
            step_results.append(result)
            if stop_on_failure and result.status == "fail" and step.required:
                break

        overall_status = "pass" if all(item.status == "pass" for item in step_results if item.status != "skipped") else "fail"
        summary = self._build_summary(overall_status, step_results)
        return CaseResult(
            case_id=self.case.meta["id"],
            status=overall_status,
            summary=summary,
            step_results=step_results,
        )

    def _run_step(self, step: Step) -> StepResult:
        if step.kind == "action":
            success, reason, evidence = self._run_action(step)
        elif step.kind == "assertion":
            success, reason, evidence = self._run_assertion(step)
        else:
            success, reason, evidence = False, f"未知步骤类型: {step.kind}", {}

        return StepResult(
            step_id=step.id,
            name=step.name,
            status="pass" if success else "fail",
            engine=step.engine,
            reason=reason,
            evidence=evidence,
        )

    def _run_action(self, step: Step) -> tuple[bool, str, Dict[str, Any]]:
        if step.engine != "computer_use":
            return False, f"动作步骤不支持引擎: {step.engine}", {}

        if step.action == "open_page":
            return self.computer_use.open_page(step.input["url"])
        if step.action == "wait":
            return self.computer_use.wait(int(step.input["seconds"]))
        if step.action == "click":
            return self.computer_use.click(step.input["target"])

        return False, f"未知动作: {step.action}", {}

    def _run_assertion(self, step: Step) -> tuple[bool, str, Dict[str, Any]]:
        if step.engine == "vision":
            if step.assertion == "object_visible":
                return self.vision.object_visible(
                    target=step.input["target"],
                    scope=step.input.get("scope", self.case.runtime.get("default_scope", "viewport")),
                )
            return False, f"未知视觉断言: {step.assertion}", {}

        if step.engine == "ocr":
            if step.assertion == "text_contains":
                return self.ocr.text_contains(
                    scope=step.input.get("scope", self.case.runtime.get("default_scope", "viewport")),
                    keywords=step.input["keywords"],
                    target=step.input["target"],
                )
            if step.assertion == "pattern_match":
                return self.ocr.pattern_match(
                    scope=step.input.get("scope", self.case.runtime.get("default_scope", "viewport")),
                    pattern=step.input["pattern"],
                    target=step.input["target"],
                )
            return False, f"未知 OCR 断言: {step.assertion}", {}

        return False, f"断言步骤不支持引擎: {step.engine}", {}

    def _build_summary(self, overall_status: str, step_results: List[StepResult]) -> str:
        passed = sum(1 for item in step_results if item.status == "pass")
        failed = sum(1 for item in step_results if item.status == "fail")
        if overall_status == "pass":
            return f"用例通过，共 {passed} 个步骤通过。"
        first_failure = next((item for item in step_results if item.status == "fail"), None)
        if first_failure is None:
            return "用例失败。"
        return f"用例失败，失败步骤: {first_failure.name}，原因: {first_failure.reason}。共 {passed} 个步骤通过，{failed} 个步骤失败。"
