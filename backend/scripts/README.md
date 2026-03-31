# 禅道 Bug 创建测试脚本

本目录包含多个用于测试禅道 Bug 创建功能的脚本。

## 脚本说明

### 1. test_create_bug.py
使用已有 Token ��建 Bug 的测试脚本。

**前置条件**：已在 `data/config.json` 中配置有效的 Token

**使用方法**：
```bash
python backend/scripts/test_create_bug.py
```

### 2. create_bug_api.py
通过后端 API 创建 Bug 的测试脚本。

**前置条件**：后端服务正在运行（`python -m uvicorn backend.main:app --reload`）

**使用方法**：
```bash
python backend/scripts/create_bug_api.py
```

### 3. refresh_token.py
先刷新 Token 再创建 Bug 的测试脚本。

**前置条件**：
- 后端服务正在运行
- 已在 `data/config.json` 中配置账号密码

**使用方法**：
```bash
python backend/scripts/refresh_token.py
```

### 4. direct_create.py ⭐ 推荐
直接通过密码获取 Token 并创建 Bug 的独立脚本（不依赖后端服务）。

**前置条件**：已在 `data/config.json` 中配置禅道账号密码

**使用方法**：
```bash
python backend/scripts/direct_create.py
```

**优点**：
- 不需要后端服务运行
- 自动获取 Token
- 显示详细执行步骤
- 成功率高

## 测试结果

使用 `direct_create.py` 成功创建了以下 Bug：
- Bug ID: 8
- 标题: 自动化测试 Bug - 数据库连接池耗尽
- 状态: active

## Bug 数据结构

所有脚本创建的 Bug 包含以下字段：

```json
{
  "product": 1,
  "title": "Bug 标题",
  "pri": 3,
  "severity": 3,
  "type": "codeerror",
  "openedBuild": "trunk",
  "steps": "复现步骤...",
  "expectedResult": "预期结果...",
  "os": "Windows 11",
  "browser": "Chrome 120"
}
```

## 故障排查

1. **连接失败**：检查网络连接和禅道地址
2. **认证失败**：检查账号密码是否正确
3. **Token 过期**：使用 `direct_create.py` 自动刷新
4. **后端 API 失败**：确保后端服务正在运行
