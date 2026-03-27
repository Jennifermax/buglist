from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class ActionType(str, Enum):
    打开页面 = "打开页面"
    输入 = "输入"
    点击 = "点击"
    等待 = "等待"
    验证 = "验证"

class TestStep(BaseModel):
    action: ActionType
    description: str
    value: Optional[str] = ""
    expected_image: Optional[str] = None

class TestCase(BaseModel):
    id: str
    name: str
    precondition: str = ""
    steps: List[TestStep]
    status: str = "pending"  # pending, approved, passed, failed

class TestCaseCreate(BaseModel):
    name: str
    precondition: str = ""
    steps: List[TestStep]
