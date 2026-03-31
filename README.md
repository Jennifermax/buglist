# Buglist

Buglist 是一个面向 UI 自动化测试的本地 MVP 平台，用来把产品文档、网页内容或图片说明转成测试用例，并通过 Playwright 执行页面操作，再结合 AI 做截图理解和结果判断。

这个仓库当前更适合做流程验证、测试设计演示和 AI + 浏览器自动化联动实验，还不是完整的生产级自动化测试平台。

## 项目现在能做什么

- 在设置页保存 OpenAI 兼容接口配置
- 从文本产品文档生成测试用例
- 从长文档分段异步生成测试用例
- 从图片和补充说明生成测试用例
- 从 URL 抓取页面正文作为生成输入
- 解析 PDF 和 DOCX 文档内容
- 直接导入 JSON 测试用例
- 在前端查看、切换和执行测试用例
- 通过 WebSocket 实时回传执行进度
- 使用 Playwright 执行基础 UI 操作
- 对验证步骤自动截图并调用 AI 做视觉判断
- 打开一个测试专用浏览器，手动登录后复用登录态执行测试
- 提供一个简单的 AI 聊天页，用来验证当前 AI 配置是否可用

## 技术栈

- 前端：Next.js 14 + React 18
- 后端：FastAPI
- 浏览器自动化：Playwright
- AI 接口：OpenAI 兼容 API
- 数据存储：本地 JSON 文件

## 目录结构

```text
buglist/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 应用入口
│   ├── config.py               # 目标站点基础地址配置
│   ├── models/                 # Pydantic 数据模型
│   ├── routers/                # API 路由
│   └── services/               # AI 服务与测试执行器
├── frontend/                   # Next.js 前端
│   ├── app/                    # 页面
│   ├── components/             # 通用组件
│   └── lib/                    # API URL 和模型配置
├── data/                       # 本地配置和测试用例数据
├── artifacts/                  # 截图、登录态等运行产物
└── docs/                       # 设计和计划文档
```

## 环境要求

- Node.js 18+
- npm 9+
- Python 3.10+

## 首次启动前准备

第一次跑项目时，通常需要完成下面三件事：

1. 安装前端依赖
2. 安装后端依赖
3. 安装 Playwright 浏览器

### 1. 安装前端依赖

```bash
cd frontend
npm install
```

### 2. 安装后端依赖

```bash
cd backend
python -m pip install -r requirements.txt
```

### 3. 安装 Playwright 浏览器

后端执行测试会启动浏览器。如果没有安装 Playwright 运行所需浏览器，执行阶段会失败。

```bash
cd backend
python -m playwright install chromium
```

如果你准备使用“测试专用浏览器登录态”能力，建议本机也安装可被 Playwright 调起的 Chrome。

## 启动方式

前后端需要分别启动。

### 启动后端

在仓库根目录执行：

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：

- API 根地址：`http://127.0.0.1:8000`

### 启动前端

另开一个终端执行：

```bash
cd frontend
npm run dev
```

启动后访问：

- 前端页面：`http://127.0.0.1:3000`

## 使用流程

### 基础流程

1. 打开设置页，填写 AI Base URL、API Key 和模型
2. 回到测试平台页，选择输入文档、上传文件、输入 URL 或上传图片说明
3. 生成测试用例
4. 审核或手动补充测试用例
5. 选择匿名模式或已登录模式执行测试
6. 查看进度、单条结果、截图和最终报告

### 已登录执行流程

如果待测页面必须先登录，建议先走这条流程：

1. 在测试平台页打开测试专用浏览器
2. 在弹出的浏览器里手动完成登录
3. 回到平台点击保存登录态
4. 执行测试时选择自动复用登录态，或者显式选择已登录模式

## 页面说明

### `/`

主测试平台页面，包含四段主流程：

- 产品文档上传
- 生成文案用例
- 生成执行用例
- 测试报告

这一页还支持：

- 上传 PDF、DOCX、Excel
- 输入网页 URL 抓取内容
- 上传图片辅助生成
- 手动输入 JSON 测试用例
- 实时查看执行进度和测试结果

### `/settings`

系统设置页，当前主要配置：

- AI 提供商
- API 地址
- API Key
- 模型名称
- 禅道配置占位

### `/chat`

一个轻量聊天页，用来验证当前 AI 配置是否可用。前端通过流式方式显示返回内容，但后端本质上还是一次性请求后再切片回传。

### `/login`

一个前端本地演示登录页，只做界面和本地登录态演示，不接后端鉴权。

## 后端 API 概览

### 配置相关

- `GET /api/config/ai`
- `POST /api/config/ai`
- `GET /api/config/zentao`
- `POST /api/config/zentao`

### 测试用例相关

- `GET /api/testcases`
- `POST /api/testcases`
- `PUT /api/testcases/{case_id}`
- `DELETE /api/testcases/{case_id}`
- `POST /api/testcases/generate`

### 异步生成任务

- `POST /api/testcase-jobs`
- `GET /api/testcase-jobs/{job_id}`

### 文档处理

- `POST /api/documents/parse`
- `POST /api/documents/fetch`

### 执行与进度

- `WS /ws/execute/{task_id}`

### 测试专用浏览器登录态

- `GET /api/browser-auth/status`
- `POST /api/browser-auth/open`
- `POST /api/browser-auth/save`
- `POST /api/browser-auth/close`

### AI 对话

- `POST /api/chat`

## 当前支持的测试步骤

后端执行器当前支持以下 action：

- `打开页面`
- `输入`
- `点击`
- `等待`
- `验证`

示例：

```json
[
  {
    "name": "登录页基础验证",
    "precondition": "测试环境可访问",
    "steps": [
      {
        "action": "打开页面",
        "description": "打开登录页面",
        "value": "https://example.com/login"
      },
      {
        "action": "输入",
        "description": "输入用户名",
        "value": "demo-user"
      },
      {
        "action": "点击",
        "description": "点击登录按钮",
        "value": "登录"
      },
      {
        "action": "验证",
        "description": "页面应显示登录成功后的内容"
      }
    ]
  }
]
```

## 执行器当前行为说明

为了避免对项目能力有误判，这里把当前执行逻辑说清楚：

- `打开页面`
  - 如果 `value` 是完整 URL，则直接访问
  - 如果 `value` 是相对路径，则会拼接基础地址
- `输入`
  - 当前通过键盘输入写入页面
  - 依赖当前焦点，不是按选择器精确输入
- `点击`
  - 会根据 `description` 和 `value` 推断按钮、链接或文本
  - 已经不是固定坐标点击，但仍属于启发式定位
- `等待`
  - 支持秒或毫秒文本，默认等待约 3 秒
- `验证`
  - 会截图并交给 AI 判断
  - 当前不是 DOM 断言，也不是像素级比对

## 默认目标站点

后端有一个默认基础地址，定义在 `backend/config.py`：

- 默认值：`https://beta-5.bydtms.com/zh`

你也可以通过环境变量覆盖：

```bash
BUGLIST_BASE_URL=https://your-site.example.com
```

当测试步骤里写的是相对路径时，执行器会基于这个地址拼接目标 URL。

## 本地数据与运行产物

### 数据文件

- `data/config.json`
  - 保存 AI 配置和禅道配置
- `data/testcases/cases.json`
  - 当前测试用例列表
- `data/testcases/demo.json`
  - 示例测试用例

### 运行产物

- `artifacts/screenshots/`
  - 执行验证步骤时生成的截图
- `artifacts/auth/storage-state.json`
  - 已保存的登录态
- `artifacts/auth/persistent-profile/`
  - 测试专用浏览器的持久化用户目录

## 当前限制

这个项目已经能跑通完整链路，但还保留明显的 MVP 特征：

- 测试用例仍保存在本地 JSON 文件，不是数据库
- `输入` 动作依赖当前焦点，不支持基于选择器的稳定输入
- `点击` 依赖文本推断和启发式定位，复杂页面上稳定性有限
- `验证` 依赖 AI 对截图做理解，不是结构化断言
- 禅道配置目前只是预留，尚未真正打通提单流程
- 聊天接口是模拟流式，不是真正的逐 token 流输出
- 测试专用浏览器能力依赖本机浏览器环境
- 当前没有完整的用户系统和后端鉴权

## 开发建议

如果你准备继续把这个项目往下做，建议优先投入在下面这些方向：

1. 为步骤增加选择器字段，替代依赖焦点输入和纯文本点击
2. 补充更稳定的断言能力，例如 DOM、URL、接口结果或文本存在性校验
3. 完善测试报告，包括完整步骤日志、失败原因和更多截图信息
4. 把测试用例和任务状态从本地 JSON 升级到数据库
5. 完成禅道集成链路
6. 增加更明确的权限、账号和项目隔离机制

## 说明

`docs/` 目录里保留了设计稿和计划稿，它们更接近开发记录。实际可运行行为请优先以当前代码和本 README 为准。
