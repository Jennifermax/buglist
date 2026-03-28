# Buglist 项目文档

## 项目概述

Buglist 是一个 AI 驱动的 UI 自动化测试平台，帮助测试工程师和开发人员快速生成和执行测试用例。

**核心功能**：
- 从产品文档自动生成测试用例
- 使用 Playwright 执行 UI 自动化测试
- AI 视觉能力进行结果判断
- 实时测试进度监控
- 测试报告生成

---

## 技术架构

### 前端技术栈

- **框架**: Next.js 14 (App Router)
- **UI 库**: React 18
- **样式**: 原生 CSS + CSS 变量系统
- **动画**: CSS Animations + Transitions
- **工具库**: XLSX (Excel 文件解析)
- **字体**: Outfit (UI), JetBrains Mono (代码)

### 后端技术栈

- **框架**: FastAPI (Python)
- **测试引擎**: Playwright
- **AI 集成**: OpenAI API / Azure OpenAI
- **通信**: WebSocket (实时进度)
- **集成**: 禅道 API (预留)

---

## 项目结构

```
buglist/
├── frontend/                    # Next.js 前端
│   ├── app/
│   │   ├── layout.js           # 根布局
│   │   ├── page.js             # 首页（测试平台）
│   │   ├── globals.css         # 全局设计系统
│   │   ├── login/              # 登录页
│   │   └── settings/           # 设置页
│   ├── components/
│   │   ├── buglist-logo.js     # SVG Logo
│   │   ├── sidebar-nav.js      # 侧边栏导航
│   │   ├── theme-toggle.js     # 主题切换
│   │   ├── auth-check.js       # 认证检查
│   │   └── animated-characters.js  # 登录动画
│   └── lib/
│       └── api.js              # API 配置
└── backend/                     # FastAPI 后端
    └── (后端代码结构)
```

---

## 设计系统

### 颜色系统

#### 渐变色
```css
--gradient-purple-blue: linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)
--gradient-pink-orange: linear-gradient(135deg, #EC4899 0%, #F59E0B 100%)
--gradient-cyan-green: linear-gradient(135deg, #06B6D4 0%, #10B981 100%)
```

#### 主题色
- **紫色**: #8B5CF6 (主色)
- **蓝色**: #3B82F6 (辅助色)
- **粉色**: #EC4899 (强调色)
- **绿色**: #10B981 (成功)
- **橙色**: #F59E0B (警告)
- **红色**: #EF4444 (危险)

#### 浅色主题
```css
--bg-primary: #fafbfc
--text-primary: #111827
--glass-bg: rgba(255, 255, 255, 0.8)
```

#### 深色主题
```css
--bg-primary: #0A0A0F
--text-primary: #f8fafc
--glass-bg: rgba(255, 255, 255, 0.05)
```

### 间距系统
```css
--radius-sm: 8px
--radius: 12px
--radius-lg: 20px
--radius-xl: 28px
```

### 阴影系统
```css
--shadow-sm: 0 1px 3px rgba(139, 92, 246, 0.08)
--shadow: 0 4px 6px -1px rgba(139, 92, 246, 0.1)
--shadow-lg: 0 10px 15px -3px rgba(139, 92, 246, 0.1)
--shadow-xl: 0 20px 25px -5px rgba(139, 92, 246, 0.1)
```

---

## 核心组件

### BuglistLogo
SVG 格式的品牌 Logo，六边形背景 + 虫子图案设计。

**特点**：
- 紫蓝渐变背景
- 白色虫子图案（头、身体、触角、腿）
- 发光效果（glow filter）
- 支持自定义大小

**使用**：
```jsx
<BuglistLogo size={32} />
```

### SidebarNav
侧边栏导航组件，包含导航项和退出登录功能。

**导航项**：
- 测试平台 (/)
- 设置 (/settings)

**功能**：
- 活跃状态指示器
- 退出登录（清除 localStorage）

### ThemeToggle
主题切换按钮，支持浅色/深色模式切换。

**特点**：
- 圆形按钮设计
- 悬停旋转动画
- localStorage 持久化
- 全局主题同步

### AuthCheck
认证检查包装组件，保护需要登录的页面。

**逻辑**：
- 检查 localStorage 中的 `isLoggedIn`
- 未登录时重定向到 `/login`
- 包装受保护的页面内容

### AnimatedCharacters
登录页的交互式动画角色组件。

**特点**：
- 4 个不同形状的角色（紫色、黑色、橙色、黄色）
- 眼睛跟随鼠标移动
- 随机眨眼动画
- 输入时角色互相看对方
- 显示密码时角色偷看

---

## 用户认证

### 登录凭证
```javascript
// 有效用户
const validUsers = ['axel', 'corn', 'felix']
const validPassword = 'qwer123'
```

### 认证流程
1. 用户输入用户名和密码
2. 前端验证凭证
3. 成功时：
   - 设置 `localStorage.setItem('isLoggedIn', 'true')`
   - 设置 `localStorage.setItem('username', username)`
   - 重定向到首页
4. 失败时：显示错误消息

### 退出登录
```javascript
localStorage.removeItem('isLoggedIn')
localStorage.removeItem('username')
router.push('/login')
```

---

## 主题系统

### 主题切换实现
```javascript
const toggleTheme = () => {
  const newTheme = theme === 'light' ? 'dark' : 'light'
  setTheme(newTheme)
  localStorage.setItem('theme', newTheme)
  document.documentElement.setAttribute('data-theme', newTheme)
}
```

### CSS 变量切换
```css
:root, [data-theme="light"] {
  /* 浅色主题变量 */
}

[data-theme="dark"] {
  /* 深色主题变量 */
}
```

### 主题持久化
- 初始化时从 localStorage 读取
- 切换时保存到 localStorage
- 设置 `data-theme` 属性到 `document.documentElement`

---

## API 集成

### API 基础配置
```javascript
// lib/api.js
export function getApiBaseUrl() {
  const hostname = window.location.hostname || '127.0.0.1'
  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
  return `${protocol}//${hostname}:8000`
}

export function getWebSocketBaseUrl() {
  const hostname = window.location.hostname || '127.0.0.1'
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${hostname}:8000`
}
```

### API 端点

#### 配置管理
```
GET  /api/config/ai       # 获取 AI 配置
POST /api/config/ai       # 保存 AI 配置
GET  /api/config/zentao   # 获取禅道配置
POST /api/config/zentao   # 保存禅道配置
```

#### 测试用例
```
POST /api/testcases/generate  # 生成测试用例
```

#### 测试执行
```
WebSocket /ws/execute/test1   # 执行测试（实时通信）
```

### WebSocket 消息格式

**发送消息**：
```json
{
  "testcases": [...],
  "ai_config": {
    "api_key": "...",
    "model": "..."
  }
}
```

**接收消息**：
```json
// 进度更新
{
  "type": "progress",
  "data": {
    "current_step": 1,
    "total_steps": 10,
    "passed": 5,
    "failed": 2
  }
}

// 完成
{
  "type": "all_complete",
  "data": {
    "total": 10,
    "passed": 8,
    "failed": 2
  }
}

// 错误
{
  "type": "error",
  "data": {
    "message": "错误信息"
  }
}
```

---

## 测试平台工作流

### 第 1 步：文件上传
- 上传产品文档（Excel）
- 或手动输入产品描述
- 系统解析文档内容

### 第 2 步：用例导入与录入
**三种方式**：
1. **上传文档**: 上传 Excel 文档，系统生成测试用例
2. **上传测试用例**: 直接上传 JSON 格式的测试用例
3. **手动输入**: 在文本框中输入 JSON 格式的测试用例

**测试用例格式**：
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
      }
    ],
    "expected_result": "成功登录并跳转到首页"
  }
]
```

### 第 3 步：执行测试
- 通过 WebSocket 连接后端
- 发送测试用例和 AI 配置
- 实时接收执行进度
- 显示通过/失败统计

### 第 4 步：测试报告
- 显示最终统计数据
- 通过率百分比
- 通过/失败用例数量
- 重新开始或提交禅道（预留）

---

## 设置页面

### AI 配置
- **API 提供商**: OpenAI / Azure / 自定义
- **API 地址**: 自定义 API 端点
- **API Key**: API 密钥
- **模型选择**: 预定义模型或自定义模型名称

### 禅道配置（预留）
- **禅道地址**: 禅道服务器地址
- **账号**: 禅道账号
- **Token**: API Token

---

## 开发指南

### 启动开发服务器
```bash
cd frontend
npm install
npm run dev
```

### 构建生产版本
```bash
npm run build
npm start
```

### 代码规范

#### 组件命名
- 使用 PascalCase：`BuglistLogo`, `SidebarNav`
- 文件名使用 kebab-case：`buglist-logo.js`, `sidebar-nav.js`

#### CSS 类命名
- 使用 kebab-case：`.brand-icon`, `.login-form`
- 组件特定类使用前缀：`.sidebar-nav`, `.theme-toggle`

#### 状态管理
- 使用 `useState` 管理组件状态
- 使用 `useEffect` 处理副作用
- 使用 localStorage 持久化数据

#### 样式组织
- 全局样式：`app/globals.css`
- 页面样式：与页面同目录的 `.css` 文件
- 组件样式：与组件同目录的 `.css` 文件

---

## 设计原则

### 1. 视觉优先，但不牺牲功能
每个设计决策都应该首先考虑视觉冲击力，但必须确保功能性和可用性不受影响。

### 2. 流动性和连贯性
界面应该像流体一样流畅，所有元素之间应该有连贯的视觉语言。

### 3. 深度和层次
通过玻璃态、阴影、模糊、3D 变换创造丰富的视觉层次。

### 4. 性能至上
所有动画和效果都必须保持 60fps，使用 GPU 加速。

### 5. 渐进增强
从简洁的基础开始，逐步添加炫酷效果，确保降级方案。

---

## 常见问题

### 如何添加新页面？
1. 在 `app/` 目录下创建新文件夹
2. 添加 `page.js` 文件
3. 在 `sidebar-nav.js` 中添加导航项

### 如何修改主题色？
1. 编辑 `app/globals.css`
2. 修改 CSS 变量值
3. 确保浅色和深色主题都更新

### 如何添加新的 API 端点？
1. 在 `lib/api.js` 中添加 API 函数
2. 在页面组件中调用 API 函数
3. 处理响应和错误

### 如何调试 WebSocket 连接？
1. 打开浏览器开发者工具
2. 查看 Network 标签的 WS 连接
3. 检查发送和接收的消息

---

## 性能优化

### 已实现的优化
- 使用 CSS 变量减少重复代码
- 动画使用 `transform` 和 `opacity`（GPU 加速）
- 组件按需加载
- WebSocket 实时通信（避免轮询）

### 待优化项
- 添加图片懒加载
- 实现代码分割
- 添加 Service Worker（PWA）
- 优化首屏加载时间

---

## 安全性考虑

### 当前实现
⚠️ **注意**：当前实现仅用于演示，生产环境需要改进：
- 硬编码的登录凭证
- localStorage 存储敏感信息
- 无 CSRF 保护
- 无速率限制

### 生产环境建议
- 使用后端认证服务
- 实现 JWT 令牌
- 使用 HttpOnly Cookie
- 添加 CSRF 令牌
- 实现速率限制
- API Key 加密存储

---

## 更新日志

### 2026-03-29
- ✅ 实现完整的设计系统（颜色、间距、阴影）
- ✅ 创建 SVG Logo 组件（六边形+虫子）
- ✅ 实现主题切换功能（浅色/深色）
- ✅ 添加登录页动画角色
- ✅ 实现品牌文字跳动动画
- ✅ 优化侧边栏导航
- ✅ 更新认证系统（3个用户）

---

## 联系方式

如有问题或建议，请联系项目维护者。

---

*最后更新: 2026-03-29*
