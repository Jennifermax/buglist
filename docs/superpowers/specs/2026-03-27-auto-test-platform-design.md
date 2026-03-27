# 自动化测试平台设计文档

## 项目概述

基于产品文档自动生成测试用例，通过 Playwright 执行 UI 自动化测试，使用 AI 视觉对比验证结果，最终生成测试报告并支持提交到禅道。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js |
| 后端 | Python FastAPI |
| 测试引擎 | Playwright (Python) |
| AI 模型 | GPT-4o /  VL /  （可配置） |
| 存储 | SQLite + 文件存储 |
| 实时通信 | WebSocket |

## 核心流程

```
文件上传 → AI生成用例 → 人工审核 → Playwright执行 → AI视觉对比 → 测试报告 → 禅道（可选）
```

## 前端设计

### 页面 1：设置页面

- AI API 配置（中转地址、API Key、模型选择）
- 禅道 API 配置（地址、账号、Token）

### 页面 2：主流程页面

使用 Step 组件展示流程进度：

```
[1.文件上传] ── [2.生成用例] ── [3.执行测试] ── [4.测试报告]
```

#### Step 1 - 文件上传

支持三种输入方式：
- 飞书文档链接
- Excel 文件上传
- 直接上传测试用例（跳过 AI 生成）

#### Step 2 - 生成用例

- AI 根据产品文档生成测试用例
- 人工审核、编辑、修改
- 保存测试用例

#### Step 3 - 执行测试

- 选择要执行的测试用例
- 实时显示执行进度（WebSocket）
- 显示每个用例的通过/失败状态

#### Step 4 - 测试报告

- 基础统计：通过数、失败数、通过率
- 可选：提交结果到禅道

## 后端设计

### API 接口

| API | 方法 | 功能 |
|-----|------|------|
| `/api/config/ai` | GET/POST | 获取/保存 AI 配置 |
| `/api/config/zentao` | GET/POST | 获取/保存禅道配置 |
| `/api/upload` | POST | 上传文件（Excel/飞书链接/测试用例） |
| `/api/testcases/generate` | POST | AI 生成测试用例 |
| `/api/testcases` | GET/POST/PUT | 获取/创建/更新测试用例 |
| `/api/testcases/execute` | POST | 执行测试 |
| `/api/reports` | GET | 获取测试报告列表 |
| `/api/reports/{id}` | GET | 获取单个报告详情 |
| `/api/zentao/submit` | POST | 提交结果到禅道 |

### WebSocket 消息

连接地址：`/ws/execute/{task_id}`

#### 进度消息

```json
{
  "type": "progress",
  "data": {
    "current_step": 3,
    "total_steps": 10,
    "current_testcase": "TC003 - 登录功能测试",
    "status": "running",
    "passed": 2,
    "failed": 0,
    "estimated_remaining_seconds": 120
  }
}
```

#### 步骤完成消息

```json
{
  "type": "step_complete",
  "data": {
    "testcase_id": "TC003",
    "testcase_name": "登录功能测试",
    "result": "passed",
    "reason": "页面显示欢迎信息，符合预期",
    "screenshot": "base64..."
  }
}
```

#### 全部完成消息

```json
{
  "type": "all_complete",
  "data": {
    "total": 10,
    "passed": 8,
    "failed": 2,
    "duration_seconds": 180
  }
}
```

## 测试用例数据结构

使用自然语言描述 + AI 视觉对比，无需 CSS 选择器：

```json
{
  "id": "TC001",
  "name": "登录功能测试",
  "precondition": "用户未登录",
  "steps": [
    {
      "action": "打开页面",
      "description": "打开登录页面",
      "value": "https://example.com/login"
    },
    {
      "action": "输入",
      "description": "在用户名输入框输入 testuser",
      "value": "testuser"
    },
    {
      "action": "点击",
      "description": "点击登录按钮"
    },
    {
      "action": "验证",
      "description": "检查是否显示欢迎信息",
      "expected_image": "base64..."
    }
  ],
  "status": "pending"
}
```

### Action 类型

| Action | 说明 | 必填字段 |
|--------|------|---------|
| `打开页面` | 导航到指定 URL | value (URL) |
| `输入` | 输入文本 | description, value |
| `点击` | 点击元素 | description |
| `等待` | 等待指定时间 | value (秒数) |
| `验证` | AI 视觉对比验证 | description, expected_image (可选) |

## AI 视觉对比流程

```
Playwright 执行操作
       │
       ▼
截取当前屏幕截图
       │
       ▼
发送给视觉 AI（截图 + 预期描述）
       │
       ▼
AI 返回判断结果
{
  "passed": true/false,
  "reason": "页面显示欢迎信息，符合预期"
}
```

## 视觉模型配置

支持多个视觉模型，可配置切换：

```python
VISION_PROVIDER = "openai"  # openai / / / baidu

async def analyze_screenshot(image, description):
    if VISION_PROVIDER == "openai":
        return await openai_vision(image, description)
    elif VISION_PROVIDER == "":
        return await (image, description)
    # ...
```

### 支持的视觉模型

| 模型 | 提供商 | 说明 |
|------|--------|------|
| GPT-4o | OpenAI | 需要支持 Vision 的 API |
|  VL | 阿里云 | 国内访问稳定 |
|  |  AI | 性价比高 |
| 文心一言 4.0 | 百度 | 支持图片理解 |

## 禅道集成（预留）

### 功能

- 提交 Bug：测试失败时自动创建 Bug 工单
- 同步用例：将测试用例同步到禅道
- 提交报告：将测试报告提交到禅道

### 配置项

```json
{
  "zentao_url": "https://your-zentao.com",
  "zentao_account": "username",
  "zentao_token": "xxx"
}
```

## 项目结构

```
buglist/
├── frontend/                # Next.js 前端
│   ├── app/
│   ├── components/
│   └── package.json
├── backend/                 # Python 后端
│   ├── main.py             # FastAPI 入口
│   ├── routers/
│   │   ├── config.py       # 配置相关 API
│   │   ├── testcases.py    # 测试用例 API
│   │   ├── upload.py       # 上传 API
│   │   └── reports.py      # 报告 API
│   ├── services/
│   │   ├── ai_service.py   # AI 生成服务
│   │   ├── vision_service.py # 视觉对比服务
│   │   ├── test_runner.py  # Playwright 执行服务
│   │   └── zentao_service.py # 禅道服务
│   ├── models/
│   └── requirements.txt
├── data/                    # 数据存储
│   ├── testcases/
│   ├── reports/
│   └── config.json
└── docs/
    └── superpowers/
        └── specs/
```

## 部署方案

### 本地开发

- 前端：`npm run dev` (localhost:3000)
- 后端：`uvicorn main:app --reload` (localhost:8000)
- Playwright：本地安装浏览器

### 后续服务器部署

- Docker 容器化
- 需要支持无头浏览器运行环境
- 任务队列（Celery + Redis）处理并发测试

## 下一步

1. 创建项目基础结构
2. 实现后端核心 API
3. 实现前端页面
4. 集成 AI 服务
5. 实现 Playwright 测试执行
6. 集成禅道 API
