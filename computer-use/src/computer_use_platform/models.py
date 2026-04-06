from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Step:
    id: str
    kind: str
    engine: str
    name: str
    required: bool
    input: Dict[str, Any]
    action: Optional[str] = None
    assertion: Optional[str] = None


@dataclass
class Case:
    meta: Dict[str, Any]
    runtime: Dict[str, Any]
    steps: List[Step]
    mock_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    step_id: str
    name: str
    status: str
    engine: str
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    case_id: str
    status: str
    summary: str
    step_results: List[StepResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "summary": self.summary,
            "steps": [
                {
                    "step_id": item.step_id,
                    "name": item.name,
                    "status": item.status,
                    "engine": item.engine,
                    "reason": item.reason,
                    "evidence": item.evidence,
                }
                for item in self.step_results
            ],
        }
