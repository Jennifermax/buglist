# 禅道自动化测试与 Bug 提交系统

一个不依赖外部框架的 Node MVP，适合在无法联网安装依赖的环境下快速演示和继续开发。

## 已实现

- 测试配置管理：项目名、禅道地址、提交模式、产品 ID、模块 ID、项目 ID、Token、账号密码、CLI 路径、自动化命令
- 用例列表展示与批量执行
- 执行记录保存
- Bug 草稿生成
- 真实禅道 Bug 提交
- 禅道连接测试
- 自动化命令预执行与日志回显

## 启动

```powershell
cd E:\buglist
npm start
```

启动后访问 `http://127.0.0.1:3000`。

## 后续接入建议

1. 优先使用 `openapi` 模式，填写 `zentaoBaseUrl`、`zentaoProductId`、`zentaoToken`。
2. 如果实例未开启 OpenAPI，可切到 `session` 模式，填写 `zentaoAccount`、`zentaoPassword`。
3. 将 `createRun` 的模拟结果替换为 Playwright、JMeter、Pytest 或接口自动化平台输出。
4. 后续可补充附件上传、执行报告导出和 Webhook 通知。

# claude
