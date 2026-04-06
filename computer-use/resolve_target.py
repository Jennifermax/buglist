from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from playwright.sync_api import sync_playwright  # noqa: E402

from computer_use_platform.ai_backend import AIVisionBackend  # noqa: E402
from computer_use_platform.config import RuntimeConfig  # noqa: E402
from computer_use_platform.element_resolver import AIElementResolver  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python3 resolve_target.py <url> <target> [click|inspect]")
        return 1

    url = sys.argv[1]
    target = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) == 4 else "inspect"

    config = RuntimeConfig.from_env()
    artifacts_dir = ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=config.headless)
        context_kwargs = {"viewport": {"width": 1280, "height": 720}, "locale": "zh-CN"}
        auth_state_path = ROOT / config.auth_state_path
        if auth_state_path.exists():
            context_kwargs["storage_state"] = str(auth_state_path)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        resolver = AIElementResolver(AIVisionBackend(config))
        result = resolver.resolve(page, target=target, action=mode, artifacts_dir=artifacts_dir, artifact_prefix="manual-resolve")
        output = {
            "found": result.found,
            "candidate_id": result.candidate_id,
            "confidence": result.confidence,
            "reason": result.reason,
            "evidence": result.evidence,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        browser.close()

    return 0 if result.found else 2


if __name__ == "__main__":
    raise SystemExit(main())
