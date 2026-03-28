# Buglist

一个面向 UI 自动化测试的 MVP 平台：根据产品文档生成测试用例，使用 Playwright 执行页面操作，再结合 AI 视觉能力做结果判断。

当前仓库的真实架构是：

- 前端：Next.js 14
- 后端：FastAPI
- 浏览器执行：Playwright
- 数据存储：本地 JSON 文件

这个项目现在更适合做流程验证和原型演示，还不是完整的生产级测试平台。

## 当前功能

- AI 配置管理
- 禅道配置占位
- 从产品文档生成测试用例
- 导入 JSON 格式测试用例
- 展示测试用例列表
- 通过 WebSocket 实时回传执行进度
- 使用 Playwright 执行基础步骤
- 使用 AI 对截图做视觉判断

## 项目结构

```text
buglist/
├── backend/                # FastAPI 后端
│   ├── main.py             # 应用入口
│   ├── routers/            # API 路由
│   ├── services/           # AI 和测试执行服务
│   └── models/             # Pydantic 数据模型
├── frontend/               # Next.js 前端
│   └── app/                # App Router 页面
├── data/                   # 本地配置和测试用例
│   ├── config.json
│   └── testcases/
└── docs/                   # 设计和计划文档
```

## 运行前准备

本项目第一次启动前，通常需要做下面 3 件事：

1. 安装前端依赖
2. 安装后端依赖
3. 安装 Playwright 浏览器

如果你只是阅读代码，不需要额外 init。

## 环境要求

- Node.js 18+
- npm 9+
- Python 3.10+

## 初始化

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

这一步很重要。后端执行测试时会启动 Chromium，如果没装浏览器，执行阶段会直接失败。

```bash
cd backend
python -m playwright install chromium
```

## 启动方式

需要分别启动前后端。

### 启动后端

在仓库根目录执行：

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- API 根地址：[http://localhost:8000](http://localhost:8000)

### 启动前端

在另一个终端执行：

```bash
cd frontend
npm run dev
```

启动后可访问：

- 前端页面：[http://localhost:3000](http://localhost:3000)

## 使用流程

1. 打开设置页，配置 AI 接口地址、API Key 和模型。
2. 回到首页，选择上传 JSON 用例，或者粘贴产品文档生成用例。
3. 审核生成结果。
4. 点击开始执行测试。
5. 在报告页查看通过数、失败数和通过率。

## 数据文件

项目当前直接使用本地 JSON 文件保存数据：

- `data/config.json`：AI 和禅道配置
- `data/testcases/cases.json`：当前测试用例列表
- `data/testcases/demo.json`：示例测试用例

仓库里已经带了示例数据，所以不需要额外建库或执行初始化脚本。

## 当前支持的测试步骤

后端当前支持这些 action：

- `打开页面`
- `输入`
- `点击`
- `等待`
- `验证`

对应的数据结构示例：

```json
[
  {
    "id": "TC001",
    "name": "登录页基础检查",
    "precondition": "测试环境可访问",
    "steps": [
      {
        "action": "打开页面",
        "description": "打开登录页",
        "value": "https://example.com/login"
      },
      {
        "action": "等待",
        "description": "等待页面加载完成",
        "value": "2"
      },
      {
        "action": "验证",
        "description": "页面应显示登录表单"
      }
    ],
    "status": "pending"
  }
]
```

## 注意事项

- 前端默认请求 `http://localhost:8000`
- 后端 CORS 当前只放行 `http://localhost:3000`
- 测试数据目前存本地文件，不是数据库
- 禅道集成目前还是预留状态
- Playwright 执行器目前是 MVP 实现
  - `点击` 还是固定坐标点击
  - `输入` 依赖当前焦点
  - `验证` 依赖 AI 看图判断，不是像素级比对

## 已知现状

这份代码目前已经能表达完整流程，但还有一些明显的原型特征：

- README 现在已按真实架构更新
- 部分前后端接口细节还需要继续对齐
- 禅道相关能力还没有真正打通
- 测试执行能力还需要补充更稳定的定位和断言方式

## 开发建议

如果你准备继续往下做，建议优先补这几块：

1. 对齐前端生成用例请求和后端接口入参
2. 为测试步骤增加选择器支持，而不是固定坐标点击
3. 补充执行日志、失败截图和详细报告
4. 完成禅道提单链路
5. 把本地 JSON 存储升级成数据库

## 和 Claude Code 计划文档的关系

`docs/` 目录下保留了设计稿和计划稿，它们更像开发过程记录。实际运行方式请以当前代码和本 README 为准。
