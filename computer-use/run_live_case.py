from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from computer_use_platform.live_runner import LiveCaseRunner, load_live_case  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 run_live_case.py <case.json>")
        return 1

    case = load_live_case(sys.argv[1])
    result = LiveCaseRunner(case).run()
    artifacts_dir = ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    result_path = artifacts_dir / f"{result['case_id']}-result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
