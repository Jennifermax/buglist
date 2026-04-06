from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from computer_use_platform.runner import CaseRunner, load_case  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
      print("Usage: python3 run_case.py <case.json>")
      return 1

    case = load_case(sys.argv[1])
    result = CaseRunner(case).run()
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
