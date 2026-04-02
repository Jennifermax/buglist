from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from typing import List
from ..models.testcase import TestCase, TestCaseBatch, TestCaseCreate

router = APIRouter(prefix="/api/testcases", tags=["testcases"])

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "testcases"

def get_cases_file() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "cases.json"


def get_batches_file() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "batches.json"

def load_testcases() -> List[TestCase]:
    file = get_cases_file()
    if file.exists():
        data = json.loads(file.read_text(encoding="utf-8"))
        return [TestCase(**item) for item in data]
    return []


def load_batches() -> List[TestCaseBatch]:
    file = get_batches_file()
    if file.exists():
        data = json.loads(file.read_text(encoding="utf-8"))
        return [TestCaseBatch(**item) for item in data]
    return []

def save_testcases(cases: List[TestCase]):
    file = get_cases_file()
    file.write_text(
        json.dumps([c.model_dump() for c in cases], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def save_batches(batches: List[TestCaseBatch]):
    file = get_batches_file()
    file.write_text(
        json.dumps([batch.model_dump() for batch in batches], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

@router.get("", response_model=List[TestCase])
async def get_testcases():
    return load_testcases()


@router.get("/batches", response_model=List[TestCaseBatch])
async def get_testcase_batches():
    batches = load_batches()
    return list(reversed(batches))


@router.get("/batches/{batch_id}", response_model=TestCaseBatch)
async def get_testcase_batch(batch_id: str):
    batches = load_batches()
    for batch in batches:
        if batch.id == batch_id:
            return batch
    raise HTTPException(status_code=404, detail="Batch not found")


@router.delete("/batches/{batch_id}")
async def delete_testcase_batch(batch_id: str):
    batches = load_batches()
    target_batch = next((batch for batch in batches if batch.id == batch_id), None)
    if not target_batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    remaining_batches = [batch for batch in batches if batch.id != batch_id]
    save_batches(remaining_batches)

    batch_case_ids = {case.id for case in (target_batch.cases or []) if getattr(case, 'id', None)}
    if batch_case_ids:
        cases = load_testcases()
        remaining_cases = [case for case in cases if case.id not in batch_case_ids]
        save_testcases(remaining_cases)

    return {"message": "batch deleted", "batch_id": batch_id}

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
