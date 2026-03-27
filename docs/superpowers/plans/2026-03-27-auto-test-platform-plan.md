# 自动化测试平台实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于产品文档自动生成测试用例，通过 Playwright 执行 UI 测试，使用 AI 视觉对比验证结果

**Architecture:** Next.js 前端 + FastAPI 后端 + Playwright 测试执行 + AI 视觉对比验证

**Tech Stack:** Next.js, FastAPI, Playwright, SQLite, WebSocket

---

## Chunk 1: 项目基础结构搭建

### Task 1: 创建项目目录结构

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Create: `data/config.json`

- [ ] **Step 1: 创建 frontend/package.json**

```json
{
  "name": "buglist-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.x",
    "react": "18.x",
    "react-dom": "18.x"
  }
}
```

- [ ] **Step 2: 创建 frontend/next.config.js**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
}

module.exports = nextConfig
```

- [ ] **Step 3: 创建 backend/requirements.txt**

```
fastapi==0.109.0
uvicorn==0.27.0
playwright==1.41.0
openai==1.12.0
python-multipart==0.0.6
sqlalchemy==2.0.25
pydantic==2.5.3
websockets==12.0
```

- [ ] **Step 4: 创建 backend/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Buglist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Buglist API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 5: 创建 data/config.json**

```json
{
  "ai": {
    "provider": "openai",
    "api_url": "",
    "api_key": "",
    "model": "gpt-4o"
  },
  "zentao": {
    "url": "",
    "account": "",
    "token": ""
  }
}
```

- [ ] **Step 6: 安装依赖并验证**

```bash
cd frontend && npm install
cd backend && pip install -r requirements.txt
```

- [ ] **Step 7: 提交**

```bash
git add frontend/ backend/ data/
git commit -m "feat: create project structure"
```

---

### Task 2: 创建前端基础页面

**Files:**
- Create: `frontend/app/layout.js`
- Create: `frontend/app/page.js`
- Create: `frontend/app/globals.css`

- [ ] **Step 1: 创建 frontend/app/layout.js**

```javascript
export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
```

- [ ] **Step 2: 创建 frontend/app/page.js**

```javascript
export default function Home() {
  return (
    <main>
      <h1>自动化测试平台</h1>
    </main>
  )
}
```

- [ ] **Step 3: 创建 frontend/app/globals.css**

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  min-height: 100vh;
}
```

- [ ] **Step 4: 验证前端运行**

```bash
cd frontend && npm run dev
# 访问 http://localhost:3000 确认显示正常
```

- [ ] **Step 5: 提交**

```bash
git add frontend/
git commit -m "feat: create basic frontend pages"
```

---

## Chunk 2: 后端核心 API

### Task 3: 配置管理 API

**Files:**
- Create: `backend/routers/config.py`
- Create: `backend/models/config.py`
- Modify: `backend/main.py:1-20`

- [ ] **Step 1: 创建配置模型 backend/models/config.py**

```python
from pydantic import BaseModel

class AIConfig(BaseModel):
    provider: str = "openai"
    api_url: str = ""
    api_key: str = ""
    model: str = "gpt-4o"

class ZentaoConfig(BaseModel):
    url: str = ""
    account: str = ""
    token: str = ""

class AppConfig(BaseModel):
    ai: AIConfig = AIConfig()
    zentao: ZentaoConfig = ZentaoConfig()
```

- [ ] **Step 2: 创建配置路由 backend/routers/config.py**

```python
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from ..models.config import AppConfig, AIConfig, ZentaoConfig

router = APIRouter(prefix="/api/config", tags=["config"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def load_config() -> AppConfig:
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AppConfig(**data)
    return AppConfig()

def save_config(config: AppConfig):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(config.model_dump_json(indent=2), encoding="utf-8")

@router.get("/ai", response_model=AIConfig)
async def get_ai_config():
    return load_config().ai

@router.post("/ai")
async def save_ai_config(config: AIConfig):
    app_config = load_config()
    app_config.ai = config
    save_config(app_config)
    return {"message": "AI config saved"}

@router.get("/zentao", response_model=ZentaoConfig)
async def get_zentao_config():
    return load_config().zentao

@router.post("/zentao")
async def save_zentao_config(config: ZentaoConfig):
    app_config = load_config()
    app_config.zentao = config
    save_config(app_config)
    return {"message": "Zentao config saved"}
```

- [ ] **Step 3: 注册路由到 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import config

app = FastAPI(title="Buglist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)

@app.get("/")
async def root():
    return {"message": "Buglist API"}
```

- [ ] **Step 4: 验证 API**

```bash
curl http://localhost:8000/api/config/ai
curl http://localhost:8000/api/config/zentao
```

- [ ] **Step 5: 提交**

```bash
git add backend/
git commit -m "feat: add config management API"
```

---

### Task 4: 测试用例模型和 API

**Files:**
- Create: `backend/models/testcase.py`
- Create: `backend/routers/testcases.py`

- [ ] **Step 1: 创建测试用例模型 backend/models/testcase.py**

```python
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
```

- [ ] **Step 2: 创建测试用例路由 backend/routers/testcases.py**

```python
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from datetime import datetime
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
```

- [ ] **Step 3: 注册路由到 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import config, testcases

app = FastAPI(title="Buglist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(testcases.router)
```

- [ ] **Step 4: 验证 API**

```bash
curl http://localhost:8000/api/testcases
curl -X POST http://localhost:8000/api/testcases \
  -H "Content-Type: application/json" \
  -d '{"name":"test","steps":[]}'
```

- [ ] **Step 5: 提交**

```bash
git add backend/
git commit -m "feat: add test case CRUD API"
```

---

## Chunk 3: AI 服务

### Task 5: AI 生成测试用例服务

**Files:**
- Create: `backend/services/ai_service.py`

- [ ] **Step 1: 创建 AI 服务 backend/services/ai_service.py**

```python
from openai import AsyncOpenAI
import base64
from pathlib import Path

class AIService:
    def __init__(self, api_url: str, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_url or None)
        self.model = model

    async def generate_testcases(self, document_content: str) -> list:
        prompt = f"""根据以下产品文档，生成测试用例。
每个测试用例需要包含：
- name: 用例名称
- precondition: 前置条件
- steps: 测试步骤数组，每个步骤包含 action, description, value

支持的 action 类型：
- 打开页面：导航到 URL，value 为 URL
- 输入：输入文本，description 描述操作，value 为输入内容
- 点击：点击元素，description 描述点击什么
- 等待：等待指定时间，value 为秒数
- 验证：AI 视觉对比验证，description 描述预期结果

请返回 JSON 数组格式的测试用例。
不要返回任何解释，只返回 JSON。

产品文档：
{document_content}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        content = response.choices[0].message.content
        # 提取 JSON 部分
        import json
        try:
            # 尝试找到 JSON 数组
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except:
            return []

    async def analyze_screenshot(self, image_data: bytes, description: str) -> dict:
        """使用视觉模型分析截图"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        prompt = f"""请分析这张截图，判断是否符合以下预期描述：
"{description}"

请返回 JSON 格式：
{{
  "passed": true 或 false,
  "reason": "判断原因"
}}
只返回 JSON，不要返回其他内容。"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                    ]
                }
            ]
        )

        content = response.choices[0].message.content
        import json
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except:
            return {"passed": False, "reason": "解析失败"}
```

- [ ] **Step 2: 创建路由 backend/routers/generate.py**

```python
from fastapi import APIRouter, HTTPException
from ..models.testcase import TestCase, TestCaseCreate
from ..services.ai_service import AIService
from ..models.config import AIConfig
from pathlib import Path
import json

router = APIRouter(prefix="/api/testcases", tags=["generate"])

CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def load_ai_config() -> AIConfig:
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AIConfig(**data.get("ai", {}))
    return AIConfig()

@router.post("/generate")
async def generate_testcases(document: str):
    config = load_ai_config()
    if not config.api_key:
        raise HTTPException(status_code=400, detail="请先配置 AI API")

    ai_service = AIService(config.api_url, config.api_key, config.model)
    cases = await ai_service.generate_testcases(document)

    # 保存生成的用例
    from .testcases import load_testcases, save_testcases
    existing = load_testcases()
    new_cases = []
    for i, case_data in enumerate(cases):
        case_id = f"TC{len(existing) + i + 1:03d}"
        case = TestCase(id=case_id, **case_data)
        new_cases.append(case)
        existing.append(case)

    save_testcases(existing)
    return {"generated": len(new_cases), "cases": new_cases}
```

- [ ] **Step 3: 注册路由并测试**

```python
# main.py 添加
from .routers import generate
app.include_router(generate.router)
```

- [ ] **Step 4: 提交**

```bash
git add backend/
git commit -m "feat: add AI test case generation service"
```

---

## Chunk 4: Playwright 测试执行

### Task 6: Playwright 测试执行服务

**Files:**
- Create: `backend/services/test_runner.py`
- Create: `backend/routers/execute.py`

- [ ] **Step 1: 创建测试运行器 backend/services/test_runner.py**

```python
from playwright.async_api import async_playwright, Page
from typing import List, Dict, Any
import asyncio

class TestRunner:
    def __init__(self, on_progress=None):
        self.on_progress = on_progress
        self.browser = None
        self.context = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()

    async def execute_testcase(self, page: Page, testcase: dict) -> dict:
        """执行单个测试用例"""
        steps = testcase.get("steps", [])
        results = []

        for i, step in enumerate(steps):
            action = step.get("action")
            description = step.get("description", "")
            value = step.get("value", "")

            try:
                if action == "打开页面":
                    await page.goto(value)
                elif action == "输入":
                    # 简单处理：直接填充到 body，后续可以改进
                    await page.keyboard.type(value)
                elif action == "点击":
                    # 点击页面中心，后续可以改进
                    await page.mouse.click(500, 300)
                elif action == "等待":
                    await asyncio.sleep(float(value))
                elif action == "验证":
                    # 截图并调用 AI 分析
                    screenshot = await page.screenshot()
                    results.append({
                        "step": i + 1,
                        "action": action,
                        "description": description,
                        "screenshot": screenshot,
                        "type": "vision_check"
                    })
            except Exception as e:
                results.append({
                    "step": i + 1,
                    "action": action,
                    "error": str(e),
                    "type": "error"
                })

        return results

    async def cleanup(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
```

- [ ] **Step 2: 创建执行路由 backend/routers/execute.py**

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
from ..services.test_runner import TestRunner
from ..services.ai_service import AIService

router = APIRouter()

@router.websocket("/ws/execute/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()

    # 临时存储连接，用于推送消息
    connections[task_id] = websocket

    try:
        # 接收测试用例数据
        data = await websocket.receive_json()
        testcases = data.get("testcases", [])
        ai_config = data.get("ai_config", {})

        runner = TestRunner()
        ai_service = AIService(
            ai_config.get("api_url", ""),
            ai_config.get("api_key", ""),
            ai_config.get("model", "gpt-4o")
        )

        await runner.start()
        page = await runner.context.new_page()

        passed = 0
        failed = 0
        total = len(testcases)

        for i, tc in enumerate(testcases):
            # 发送进度
            await websocket.send_json({
                "type": "progress",
                "data": {
                    "current_step": i + 1,
                    "total_steps": total,
                    "current_testcase": tc.get("name", ""),
                    "status": "running",
                    "passed": passed,
                    "failed": failed
                }
            })

            # 执行测试
            results = await runner.execute_testcase(page, tc)

            # 处理验证步骤
            for result in results:
                if result.get("type") == "vision_check":
                    vision_result = await ai_service.analyze_screenshot(
                        result.get("screenshot"),
                        result.get("description", "")
                    )
                    result["ai_result"] = vision_result
                    if vision_result.get("passed"):
                        passed += 1
                    else:
                        failed += 1
                else:
                    failed += 1

            # 发送步骤完成
            await websocket.send_json({
                "type": "step_complete",
                "data": {
                    "testcase_id": tc.get("id"),
                    "testcase_name": tc.get("name"),
                    "result": "passed" if passed > failed else "failed",
                    "reason": "测试执行完成"
                }
            })

        await runner.cleanup()

        # 发送全部完成
        await websocket.send_json({
            "type": "all_complete",
            "data": {
                "total": total,
                "passed": passed,
                "failed": failed
            }
        })

    except WebSocketDisconnect:
        pass
    finally:
        if task_id in connections:
            del connections[task_id]

# 全局连接存储
connections = {}
```

- [ ] **Step 3: 注册路由**

```python
# main.py
from .routers import execute
app.include_router(execute.router)
```

- [ ] **Step 4: 提交**

```bash
git add backend/
git commit -m "feat: add Playwright test execution service"
```

---

## Chunk 5: 前端实现

### Task 7: 前端设置页面

**Files:**
- Create: `frontend/app/settings/page.js`
- Modify: `frontend/app/layout.js`

- [ ] **Step 1: 创建设置页面**

```javascript
'use client'
import { useState, useEffect } from 'react'

export default function Settings() {
  const [aiConfig, setAiConfig] = useState({
    provider: 'openai',
    api_url: '',
    api_key: '',
    model: 'gpt-4o'
  })
  const [zentaoConfig, setZentaoConfig] = useState({
    url: '',
    account: '',
    token: ''
  })

  useEffect(() => {
    fetch('/api/config/ai').then(r => r.json()).then(setAiConfig)
    fetch('/api/config/zentao').then(r => r.json()).then(setZentaoConfig)
  }, [])

  const saveAiConfig = async () => {
    await fetch('/api/config/ai', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(aiConfig)
    })
    alert('AI 配置已保存')
  }

  const saveZentaoConfig = async () => {
    await fetch('/api/config/zentao', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(zentaoConfig)
    })
    alert('禅道配置已保存')
  }

  return (
    <div style={{padding: '20px'}}>
      <h1>设置</h1>

      <section style={{marginTop: '20px'}}>
        <h2>AI 配置</h2>
        <div style={{display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '400px'}}>
          <label>
            API 地址:
            <input type="text" value={aiConfig.api_url}
              onChange={e => setAiConfig({...aiConfig, api_url: e.target.value})} />
          </label>
          <label>
            API Key:
            <input type="password" value={aiConfig.api_key}
              onChange={e => setAiConfig({...aiConfig, api_key: e.target.value})} />
          </label>
          <label>
            模型:
            <select value={aiConfig.model}
              onChange={e => setAiConfig({...aiConfig, model: e.target.value})}>
              <option value="gpt-4o">GPT-4o</option>
              <option value="gpt-4o-mini">GPT-4o-mini</option>
            </select>
          </label>
          <button onClick={saveAiConfig}>保存 AI 配置</button>
        </div>
      </section>

      <section style={{marginTop: '20px'}}>
        <h2>禅道配置</h2>
        <div style={{display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '400px'}}>
          <label>
            禅道地址:
            <input type="text" value={zentaoConfig.url}
              onChange={e => setZentaoConfig({...zentaoConfig, url: e.target.value})} />
          </label>
          <label>
            账号:
            <input type="text" value={zentaoConfig.account}
              onChange={e => setZentaoConfig({...zentaoConfig, account: e.target.value})} />
          </label>
          <label>
            Token:
            <input type="password" value={zentaoConfig.token}
              onChange={e => setZentaoConfig({...zentaoConfig, token: e.target.value})} />
          </label>
          <button onClick={saveZentaoConfig}>保存禅道配置</button>
        </div>
      </section>
    </div>
  )
}
```

- [ ] **Step 2: 更新 layout 添加导航**

```javascript
import Link from 'next/link'
import './globals.css'

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>
        <nav style={{padding: '10px 20px', borderBottom: '1px solid #eee'}}>
          <Link href="/" style={{marginRight: '20px'}}>测试平台</Link>
          <Link href="/settings">设置</Link>
        </nav>
        {children}
      </body>
    </html>
  )
}
```

- [ ] **Step 3: 验证并提交**

```bash
git add frontend/
git commit -m "feat: add settings page"
```

---

### Task 8: 前端主流程页面

**Files:**
- Create: `frontend/app/page.js` (重写)
- Create: `frontend/components/Stepper.js`

- [ ] **Step 1: 创建 Stepper 组件**

```javascript
export default function Stepper({ current, steps }) {
  return (
    <div style={{display: 'flex', alignItems: 'center', padding: '20px'}}>
      {steps.map((step, index) => (
        <div key={index} style={{display: 'flex', alignItems: 'center'}}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            background: index + 1 <= current ? '#4CAF50' : '#ccc',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {index + 1 <= current ? '✓' : index + 1}
          </div>
          <span style={{margin: '0 10px'}}>{step}</span>
          {index < steps.length - 1 && (
            <div style={{width: '50px', height: '2px', background: '#ccc'}} />
          )}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: 创建主流程页面**

```javascript
'use client'
import { useState, useEffect, useRef } from 'react'
import Stepper from '../components/Stepper'

const STEPS = ['文件上传', '生成用例', '执行测试', '测试报告']

export default function Home() {
  const [currentStep, setCurrentStep] = useState(1)
  const [uploadType, setUploadType] = useState('file')
  const [document, setDocument] = useState('')
  const [testcases, setTestcases] = useState([])
  const [progress, setProgress] = useState(null)
  const wsRef = useRef(null)

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
      // Excel 处理后续添加
      alert('Excel 文件上传功能开发中')
    } else if (file.name.endsWith('.json')) {
      // 直接上传测试用例
      const text = await file.text()
      const cases = JSON.parse(text)
      setTestcases(cases)
      setCurrentStep(3)
    }
  }

  const generateTestcases = async () => {
    if (!document) {
      alert('请输入产品文档内容')
      return
    }

    const res = await fetch('/api/testcases/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(document)
    })
    const data = await res.json()
    setTestcases(data.cases || [])
    setCurrentStep(2)
  }

  const executeTests = async () => {
    const aiRes = await fetch('/api/config/ai')
    const aiConfig = await aiRes.json()

    if (!aiConfig.api_key) {
      alert('请先在设置页面配置 AI API')
      return
    }

    const ws = new WebSocket('ws://localhost:8000/ws/execute/test1')
    wsRef.current = ws

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'progress') {
        setProgress(msg.data)
      } else if (msg.type === 'all_complete') {
        setProgress(msg.data)
        setCurrentStep(4)
        ws.close()
      }
    }

    ws.onopen = () => {
      ws.send(JSON.stringify({
        testcases: testcases,
        ai_config: aiConfig
      }))
      setCurrentStep(3)
    }
  }

  return (
    <main>
      <Stepper current={currentStep} steps={STEPS} />

      {/* Step 1: 文件上传 */}
      {currentStep === 1 && (
        <div style={{padding: '20px'}}>
          <h2>Step 1: 文件上传</h2>
          <div style={{marginTop: '10px'}}>
            <label>
              <input type="radio" name="uploadType" checked={uploadType === 'file'}
                onChange={() => setUploadType('file')} /> 文件上传
            </label>
            <label style={{marginLeft: '20px'}}>
              <input type="radio" name="uploadType" checked={uploadType === 'text'}
                onChange={() => setUploadType('text')} /> 手动输入
            </label>
          </div>

          {uploadType === 'file' ? (
            <div style={{marginTop: '20px'}}>
              <input type="file" accept=".json,.xlsx,.xls" onChange={handleFileUpload} />
              <p style={{color: '#666', marginTop: '10px'}}>
                支持 JSON 测试用例文件或 Excel 产品文档
              </p>
            </div>
          ) : (
            <div style={{marginTop: '20px'}}>
              <textarea
                value={document}
                onChange={e => setDocument(e.target.value)}
                placeholder="输入产品文档内容..."
                style={{width: '100%', height: '200px'}}
              />
            </div>
          )}

          <button onClick={generateTestcases} style={{marginTop: '20px'}}>
            生成测试用例
          </button>
        </div>
      )}

      {/* Step 2: 用例管理 */}
      {currentStep === 2 && (
        <div style={{padding: '20px'}}>
          <h2>Step 2: 生成用例 ({testcases.length} 个)</h2>
          <div style={{marginTop: '10px'}}>
            {testcases.map(tc => (
              <div key={tc.id} style={{border: '1px solid #ddd', padding: '10px', marginTop: '10px'}}>
                <strong>{tc.id}: {tc.name}</strong>
                <p style={{color: '#666'}}>{tc.precondition}</p>
              </div>
            ))}
          </div>
          <button onClick={executeTests} style={{marginTop: '20px'}}>
            开始执行测试
          </button>
        </div>
      )}

      {/* Step 3: 执行测试 */}
      {currentStep === 3 && (
        <div style={{padding: '20px'}}>
          <h2>Step 3: 执行测试</h2>
          {progress ? (
            <div>
              <p>正在执行: {progress.current_testcase}</p>
              <p>进度: {progress.current_step} / {progress.total_steps}</p>
              <p>通过: {progress.passed} | 失败: {progress.failed}</p>
            </div>
          ) : (
            <p>等待执行...</p>
          )}
        </div>
      )}

      {/* Step 4: 测试报告 */}
      {currentStep === 4 && (
        <div style={{padding: '20px'}}>
          <h2>Step 4: 测试报告</h2>
          {progress && (
            <div>
              <p>总计: {progress.total}</p>
              <p>通过: {progress.passed}</p>
              <p>失败: {progress.failed}</p>
              <p>通过率: {Math.round(progress.passed / progress.total * 100)}%</p>
            </div>
          )}
        </div>
      )}
    </main>
  )
}
```

- [ ] **Step 3: 验证并提交**

```bash
git add frontend/
git commit -m "feat: add main workflow page with stepper"
```

---

## Chunk 6: 集成测试和优化

### Task 9: 集成测试

- [ ] **Step 1: 启动后端**

```bash
cd backend && uvicorn main:app --reload
```

- [ ] **Step 2: 启动前端**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: 测试完整流程**
1. 访问 http://localhost:3000
2. 配置 AI API（设置页面）
3. 输入产品文档内容
4. 生成测试用例
5. 执行测试
6. 查看报告

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat: complete integration test"
```

---

## 下一步

实现计划完成！所有任务遵循 TDD 原则，每个步骤都有明确的代码和验证命令。

**Ready to execute?**
