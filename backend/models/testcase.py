from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class ActionType(str, Enum):
    打开页面 = "打开页面"
    输入 = "输入"
    点击 = "点击"
    等待 = "等待"
    验证 = "验证"

class TestStep(BaseModel):
    action: str
    description: str = ""
    value: Optional[str] = ""
    expected_image: Optional[str] = None

class TestCase(BaseModel):
    id: str
    case_no: str = ""
    priority: str = "P1"
    name: str
    precondition: str = ""
    test_data: str = ""
    expected_result: str = ""
    owner: str = ""
    remarks: str = ""
    steps: List[TestStep]
    status: str = "pending"  # pending, approved, passed, failed

class TestCaseCreate(BaseModel):
    case_no: str = ""
    priority: str = "P1"
    name: str
    precondition: str = ""
    test_data: str = ""
    expected_result: str = ""
    owner: str = ""
    remarks: str = ""
    steps: List[TestStep]


class TestCaseBatch(BaseModel):
    id: str
    created_at: str
    source_name: str = ""
    source_document: str = ""
    generated_count: int = 0
    status: str = "completed"
    cases: List[TestCase] = Field(default_factory=list)
