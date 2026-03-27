from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import List
from ..models.testcase import TestCase, TestCaseCreate

router = APIRouter(prefix="/api/testcases", tags=["testcases"])

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "testcases"

def get_cases_file() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "cases.json"

def load_testcases() -> List[TestCase]:
    file = get_cases_file()
    if file.exists():
        data = json.loads(file.read_text(encoding="utf-8"))
        return [TestCase(**item) for item in data]
    return []

def save_testcases(cases: List[TestCase]):
    file = get_cases_file()
    file.write_text(
        json.dumps([c.model_dump() for c in cases], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

@router.get("", response_model=List[TestCase])
async def get_testcases():
    return load_testcases()

@router.post("")
async def create_testcase(case: TestCaseCreate):
    cases = load_testcases()
    case_id = f"TC{len(cases) + 1:03d}"
    new_case = TestCase(id=case_id, **case.model_dump())
    cases.append(new_case)
    save_testcases(cases)
    return new_case

@router.put("/{case_id}")
async def update_testcase(case_id: str, case: TestCase):
    cases = load_testcases()
    for i, c in enumerate(cases):
        if c.id == case_id:
            cases[i] = case
            save_testcases(cases)
            return case
    raise HTTPException(status_code=404, detail="Test case not found")

@router.delete("/{case_id}")
async def delete_testcase(case_id: str):
    cases = load_testcases()
    cases = [c for c in cases if c.id != case_id]
    save_testcases(cases)
    return {"message": "deleted"}
