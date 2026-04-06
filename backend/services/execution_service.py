from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ..computer_use_platform.config import RuntimeConfig
from ..computer_use_platform.live_runner import LiveCaseRunner
from ..config import get_base_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = PROJECT_ROOT / "artifacts" / "screenshots"
AUTH_STATE_FILE = PROJECT_ROOT / "artifacts" / "auth" / "storage-state.json"


def build_runtime_config(ai_config: Dict[str, Any], *, reuse_auth_state: bool) -> RuntimeConfig:
    values = {
        "COMPUTER_USE_AI_PROVIDER": "openai_compatible",
        "COMPUTER_USE_AI_API_KEY": str(ai_config.get("api_key", "") or ""),
        "COMPUTER_USE_AI_BASE_URL": str(ai_config.get("api_url", "") or "https://api.openai.com/v1"),
        "COMPUTER_USE_AI_MODEL": str(ai_config.get("model", "") or "gpt-5.4-mini"),
        "COMPUTER_USE_AI_TIMEOUT": "60",
        "COMPUTER_USE_HEADLESS": "true",
        "COMPUTER_USE_AUTH_STATE_PATH": str(AUTH_STATE_FILE) if reuse_auth_state else "",
        "COMPUTER_USE_AUTH_URL": f"{get_base_url().rstrip('/')}/login",
    }
    return RuntimeConfig.from_mapping(values)


def run_testcase(testcase: Dict[str, Any], ai_config: Dict[str, Any], *, reuse_auth_state: bool) -> Dict[str, Any]:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    runtime_config = build_runtime_config(ai_config, reuse_auth_state=reuse_auth_state)
    runner = LiveCaseRunner(
        testcase,
        artifacts_dir=str(SCREENSHOT_DIR),
        runtime_config=runtime_config,
    )
    result = runner.run()
    _retain_decisive_artifact(result)
    return result


def build_step_complete_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    screenshots = _collect_screenshots(result.get("steps", []))
    vision_details = _collect_ai_details(result.get("steps", []))
    failed_step = next((item for item in result.get("steps", []) if item.get("status") == "fail"), None)
    reason = failed_step.get("reason") if failed_step else result.get("summary", "")

    return {
        "testcase_id": result.get("case_id"),
        "testcase_name": result.get("case_name") or result.get("case_id"),
        "result": "passed" if result.get("status") == "pass" else "failed",
        "reason": reason,
        "vision_details": vision_details,
        "screenshots": screenshots,
    }


def _collect_ai_details(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    details: List[Dict[str, Any]] = []
    for step in steps:
        evidence = step.get("evidence") or {}
        if evidence.get("engine") == "ai":
            details.append(
                {
                    "passed": step.get("status") == "pass",
                    "reason": step.get("reason", ""),
                }
            )
        elif evidence.get("ai"):
            ai_info = evidence["ai"]
            details.append(
                {
                    "passed": step.get("status") == "pass",
                    "reason": ai_info.get("reason") or step.get("reason", ""),
                }
            )
    return details


def _collect_screenshots(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected = _select_decisive_step(steps)
    if not selected:
        return []

    evidence = selected.get("evidence") or {}
    screenshot = evidence.get("screenshot")
    if not screenshot:
        return []

    path = Path(screenshot)
    if not path.exists():
        return []
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return []

    try:
        relative = path.resolve().relative_to(PROJECT_ROOT.resolve())
    except Exception:
        return []

    return [
        {
            "name": path.name,
            "url": f"/{relative.as_posix()}",
            "description": selected.get("name", ""),
            "action": selected.get("step_id", ""),
        }
    ]


def _retain_decisive_artifact(result: Dict[str, Any]) -> None:
    case_id = str(result.get("case_id") or "").strip()
    if not case_id:
        return

    selected = _select_decisive_step(result.get("steps", []))
    keep_path = None
    if selected:
        keep_path = _extract_existing_artifact_path(selected)

    for artifact in SCREENSHOT_DIR.glob(f"{case_id}-*"):
        if keep_path is not None and artifact.resolve() == keep_path.resolve():
            continue
        if not artifact.is_file():
            continue
        try:
            artifact.unlink()
        except FileNotFoundError:
            continue


def _select_decisive_step(steps: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    failed_with_artifact = next(
        (
            step
            for step in steps
            if step.get("status") == "fail" and _extract_existing_artifact_path(step) is not None
        ),
        None,
    )
    if failed_with_artifact is not None:
        return failed_with_artifact

    for step in reversed(steps):
        if step.get("status") == "pass" and _extract_existing_artifact_path(step) is not None:
            return step

    for step in reversed(steps):
        if _extract_existing_artifact_path(step) is not None:
            return step

    return None


def _extract_existing_artifact_path(step: Dict[str, Any]) -> Path | None:
    evidence = step.get("evidence") or {}
    screenshot = evidence.get("screenshot")
    if not screenshot:
        return None

    path = Path(screenshot)
    if not path.exists():
        return None
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    return path
