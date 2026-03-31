# -*- coding: utf-8 -*-
"""
直接创建 Bug 到禅道
"""
import asyncio
import httpx
import json
from pathlib import Path

# 读取配置
CONFIG_FILE = Path(__file__).parent.parent / "data" / "config.json"
config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
zentao_config = config_data["zentao"]

base_url = zentao_config["url"].rstrip('/')
account = zentao_config["account"]
password = zentao_config["password"]

async def main():
    """主函数"""

    print("=" * 60)
    print("禅道 Bug 创建工具")
    print("=" * 60)

    # 第一步：获取 Token
    print("\n[1/3] 正在获取 Token...")

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        # 获取 Token
        token_response = await client.post(
            f"{base_url}/api.php/v1/tokens",
            json={"account": account, "password": password}
        )

        if token_response.status_code not in [200, 201]:
            print(f"获取 Token 失败: {token_response.status_code}")
            print(f"响应: {token_response.text}")
            return

        token_data = token_response.json()
        if "token" not in token_data:
            print(f"Token 响应无效: {token_data}")
            return

        token = token_data["token"]
        print(f"Token: {token[:10]}... (成功)")

        # 第二步：获取产品列表
        print("\n[2/3] 获取产品列表...")

        headers = {
            "Content-Type": "application/json",
            "Token": token,
            "zentao": account
        }

        products_response = await client.get(
            f"{base_url}/api.php/v1/products",
            headers=headers
        )

        if products_response.status_code == 200:
            products_data = products_response.json()
            products = products_data.get("products", []) if isinstance(products_data, dict) else products_data
            print(f"找到 {len(products)} 个产品")
            if products:
                print(f"第一个产品: {products[0].get('name', 'N/A')} (ID: {products[0].get('id', 'N/A')})")
        else:
            print(f"获取产品失败: {products_response.status_code}")

        # 第三步：创建 Bug
        print("\n[3/3] 创建 Bug...")

        bug_data = {
            "product": 1,
            "title": "自动化测试 Bug - 数据库连接池耗尽",
            "pri": 3,
            "severity": 3,
            "type": "codeerror",
            "openedBuild": "trunk",
            "steps": """1. 启动后端服务
2. 并发执行 10 个测试用例
3. 观察日志

实际结果：部分测试失败，错误信息 "Database connection pool exhausted"
预期结果：所有测试正常执行""",
            "expectedResult": "所有测试正常执行",
            "os": "Windows 11",
            "browser": "Chrome 120"
        }

        print(f"标题: {bug_data['title']}")
        print(f"优先级: {bug_data['pri']}, 严重程度: {bug_data['severity']}")

        create_response = await client.post(
            f"{base_url}/api.php/v1/bugs?product=1",
            headers=headers,
            json=bug_data
        )

        print(f"\n状态码: {create_response.status_code}")
        result_data = create_response.json()

        if create_response.status_code in [200, 201] and "error" not in result_data:
            print("\n" + "=" * 60)
            print("成功创建 Bug！")
            print("=" * 60)
            print(f"Bug ID: {result_data.get('id', 'N/A')}")
            print(f"标题: {result_data.get('title', bug_data['title'])}")
            print(f"状态: {result_data.get('status', 'N/A')}")
            print("=" * 60)
        else:
            print(f"\n创建失败: {result_data}")

if __name__ == "__main__":
    asyncio.run(main())
