from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from playwright.sync_api import sync_playwright  # noqa: E402

from computer_use_platform.config import RuntimeConfig  # noqa: E402


def main() -> int:
    config = RuntimeConfig.from_env()
    state_path = ROOT / config.auth_state_path
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context_kwargs = {"viewport": {"width": 1280, "height": 720}, "locale": "zh-CN"}
        if state_path.exists():
            context_kwargs["storage_state"] = str(state_path)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.goto(config.auth_url, wait_until="domcontentloaded", timeout=60000)

        print("浏览器已打开。请在浏览器里完成登录。")
        print("登录完成后，回到这里按回车，我会保存登录状态。")
        input()

        context.storage_state(path=str(state_path))
        print(f"登录状态已保存到: {state_path}")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
