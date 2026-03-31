"""
测试创建 Bug 到禅道
"""
import asyncio
import httpx
import json
import sys
from pathlib import Path

# 设置控制台输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 读取配置
CONFIG_FILE = Path(__file__).parent.parent / "data" / "config.json"
config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
zentao_config = config_data["zentao"]

base_url = zentao_config["url"].rstrip('/')
account = zentao_config["account"]
token = zentao_config["token"]

async def create_test_bug():
    """创建测试 Bug"""
    headers = {
        "Content-Type": "application/json",
        "Token": token,
        "zentao": account
    }

    # 构建测试 Bug 数据
    bug_data = {
        "product": 1,
        "title": "自动化测试 Bug - 登录页面样式异常",
        "pri": 3,  # 优先级：3(中)
        "severity": 3,  # 严重程度：3(中)
        "type": "codeerror",  # 类型：代码错误
        "openedBuild": "trunk",
        "steps": """1. 打开登录页面 /login
2. 输入用户名和密码
3. 点击登录按钮

实际结果：登录按钮点击后无响应，控制台报错 TypeError: Cannot read property 'classList' of undefined
预期结果：成功登录并跳转到首页""",
        "expectedResult": "成功登录并跳转到首页",
        "os": "Windows 11",
        "browser": "Chrome 120"
    }

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        # 首先测试连接
        print("🔍 测试禅道连接...")
        response = await client.get(
            f"{base_url}/api.php/v1/products",
            headers=headers
        )
        if response.status_code == 200:
            print("✅ 连接成功！")
        else:
            print(f"❌ 连接失败: {response.status_code}")
            return

        # 创建 Bug
        print(f"\n📝 创建 Bug...")
        print(f"标题: {bug_data['title']}")
        print(f"优先级: {bug_data['pri']}")
        print(f"严重程度: {bug_data['severity']}")

        response = await client.post(
            f"{base_url}/api.php/v1/bugs?product=1",
            headers=headers,
            json=bug_data
        )

        print(f"\n状态码: {response.status_code}")
        print(f"响应: {response.text}")

        if response.status_code in [200, 201]:
            result = response.json()
            if "error" not in result:
                print(f"\n✅ Bug 创建成功！")
                print(f"Bug ID: {result.get('id', 'N/A')}")
                print(f"标题: {result.get('title', bug_data['title'])}")
            else:
                print(f"\n❌ 创建失败: {result['error']}")
        else:
            print(f"\n❌ 创建失败")

if __name__ == "__main__":
    print("=" * 60)
    print("禅道 Bug 创建测试")
    print("=" * 60)
    print(f"禅道地址: {base_url}")
    print(f"账号: {account}")
    print(f"Token: {token[:10]}..." if len(token) > 10 else f"Token: {token}")
    print("=" * 60)

    asyncio.run(create_test_bug())
