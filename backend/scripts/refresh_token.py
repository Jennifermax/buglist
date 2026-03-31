"""
刷新禅道 Token 并创建 Bug
"""
import requests
import json

API_BASE = "http://127.0.0.1:8000"

print("=" * 60)
print("1. 测试禅道连接并刷新 Token")
print("=" * 60)

try:
    # 测试连接，会自动刷新 Token
    response = requests.post(f"{API_BASE}/api/zentao/test-connection", timeout=10)
    result = response.json()
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

    if result.get("success"):
        print("\nToken 刷新成功！")

        print("\n" + "=" * 60)
        print("2. 创建新 Bug")
        print("=" * 60)

        bug_data = {
            "product": 1,
            "title": "自动化测试 Bug - API 响应超时",
            "pri": 3,
            "severity": 3,
            "type": "codeerror",
            "openedBuild": "trunk",
            "steps": """1. 调用 /api/testcases/generate 接口
2. 上传大文件（>5MB）

实际结果：请求超过 30 秒后超时
预期结果：正常返回生成的测试用例 """,
            "expectedResult": "正常返回测试用例",
            "os": "Windows 11",
            "browser": "Chrome 120"
        }

        print(f"Bug 标题: {bug_data['title']}")

        # 创建 Bug
        response = requests.post(
            f"{API_BASE}/api/zentao/bugs",
            json=bug_data,
            timeout=10
        )

        result = response.json()
        print(f"\n响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

        if result.get("success"):
            print("\n成功！Bug 已创建到禅道")
            if "data" in result and isinstance(result["data"], dict):
                bug_id = result["data"].get("id")
                if bug_id:
                    print(f"Bug ID: {bug_id}")
        else:
            print(f"\n失败: {result.get('message')}")

except requests.exceptions.ConnectionError:
    print("连接失败：请确保后端服务正在运行")
except Exception as e:
    print(f"错误: {e}")
