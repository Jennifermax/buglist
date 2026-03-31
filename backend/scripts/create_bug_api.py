"""
通过后端 API 创建 Bug
"""
import requests
import json

# API 基础地址
API_BASE = "http://127.0.0.1:8000"

# Bug 数据
bug_data = {
    "product": 1,
    "title": "自动化测试 Bug - 用户权限验证问题",
    "pri": 3,
    "severity": 3,
    "type": "codeerror",
    "openedBuild": "trunk",
    "steps": """1. 登录系统
2. 访问 /settings 页面
3. 修改 AI 配置并保存

实际结果：配置保存失败，控制台报错 403 Forbidden
预期结果：配置成功保存并提示"保存成功" """,
    "expectedResult": "配置成功保存",
    "os": "Windows 11",
    "browser": "Chrome 120"
}

print("=" * 60)
print("通过后端 API 创建禅道 Bug")
print("=" * 60)
print(f"API 地址: {API_BASE}")
print(f"Bug 标题: {bug_data['title']}")
print("=" * 60)

try:
    # 发送请求
    response = requests.post(
        f"{API_BASE}/api/zentao/bugs",
        json=bug_data,
        timeout=10
    )

    print(f"\n状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            print(f"\n✅ Bug 创建成功！")
            if "data" in result and isinstance(result["data"], dict):
                bug_id = result["data"].get("id")
                if bug_id:
                    print(f"Bug ID: {bug_id}")
        else:
            print(f"\n❌ 创建失败: {result.get('message')}")
    else:
        print(f"\n❌ 请求失败: {response.status_code}")

except requests.exceptions.ConnectionError:
    print("\n❌ 连接失败：请确保后端服务正在运行")
    print("启动命令: cd backend && python -m uvicorn main:app --reload")
except Exception as e:
    print(f"\n❌ 错误: {str(e)}")
