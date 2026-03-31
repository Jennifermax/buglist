"""
禅道初始化服务
每次启动时从 login.txt 读取禅道配置并自动连接
"""
import re
from pathlib import Path
from urllib.parse import urlparse
from .zentao_service import ZentaoService
from ..models.config import ZentaoConfig

LOGIN_FILE = Path(__file__).parent.parent.parent / "login.txt"
CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "config.json"

def parse_login_file() -> dict:
    """解析 login.txt 文件"""
    if not LOGIN_FILE.exists():
        print(f"[Zentao Init] login.txt 文件不存在: {LOGIN_FILE}")
        return {}

    content = LOGIN_FILE.read_text(encoding="utf-8")
    result = {}

    # 解析网址（只取域名部分）
    url_match = re.search(r'禅道网址[：:]\s*(https?://[^\s\n]+)', content)
    if url_match:
        full_url = url_match.group(1).strip()
        # 解析 URL，只保留 scheme + host
        parsed = urlparse(full_url)
        result['url'] = f"{parsed.scheme}://{parsed.netloc}"

    # 解析账号
    account_match = re.search(r'account\s*=\s*"?([^"\s]+)"?', content)
    if account_match:
        result['account'] = account_match.group(1).strip()

    # 解析密码
    password_match = re.search(r'password\s*=\s*"?([^"\s]+)"?', content)
    if password_match:
        result['password'] = password_match.group(1).strip()

    return result

def save_zentao_config(config: dict):
    """保存禅道配置到 config.json"""
    import json

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {"ai": {}, "zentao": {}}

    # 更新禅道配置
    data["zentao"] = {
        "url": config.get("url", ""),
        "account": config.get("account", ""),
        "password": config.get("password", ""),
        "token": config.get("token", "")
    }

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def init_zentao():
    """
    初始化禅道连接
    从 login.txt 读取配置，登录获取 Token，并保存配置
    """
    print("[Zentao Init] 开始初始化禅道...")

    # 1. 解析 login.txt
    login_info = parse_login_file()
    if not login_info:
        print("[Zentao Init] 未找到有效的禅道配置")
        return None

    required_fields = ['url', 'account', 'password']
    for field in required_fields:
        if field not in login_info or not login_info[field]:
            print(f"[Zentao Init] 缺少必填字段: {field}")
            return None

    print(f"[Zentao Init] 读取配置: URL={login_info['url']}, Account={login_info['account']}")

    # 2. 创建临时服务获取 Token
    temp_config = ZentaoConfig(
        url=login_info['url'],
        account=login_info['account'],
        password=login_info['password'],
        token=""
    )

    service = ZentaoService(temp_config)

    try:
        # 3. 通过密码登录获取 Token
        print("[Zentao Init] 正在登录禅道...")
        token_result = await service.get_token_by_password(login_info['password'])

        if token_result.get('success'):
            token = token_result['token']
            print(f"[Zentao Init] 登录成功，Token: {token[:10]}...")

            # 4. 保存配置
            login_info['token'] = token
            save_zentao_config(login_info)
            print("[Zentao Init] 配置已保存到 data/config.json")

            # 5. 测试连接
            test_result = await service.test_connection()
            if test_result.get('success'):
                print("[Zentao Init] 连接测试成功!")
                # 返回服务实例，不关闭它
                return service
            else:
                print(f"[Zentao Init] 连接测试失败: {test_result.get('message')}")
                await service.close()
                return None
        else:
            print(f"[Zentao Init] 登录失败: {token_result.get('message')}")
            await service.close()
            return None

    except Exception as e:
        print(f"[Zentao Init] 初始化失败: {e}")
        await service.close()
        return None

async def create_test_bug(service: ZentaoService, product_id: int = 1):
    """
    创建测试 Bug
    """
    try:
        bug_data = {
            "product": product_id,
            "title": "[Buglist 自动测试] 验证禅道集成功能",
            "pri": 3,
            "severity": 3,
            "type": "codeerror",
            "steps": "1. 打开 Buglist 系统\n2. 系统自动读取 login.txt\n3. 自动连接禅道\n预期：连接成功，Bug 创建成功",
            "expectedResult": "禅道集成功能正常工作"
        }

        result = await service.create_bug(bug_data)
        if result.get('success'):
            bug = result['data']
            print(f"[Zentao Init] 测试 Bug 创建成功! ID: {bug.get('id')}, Title: {bug.get('title')}")
            return bug
        else:
            print(f"[Zentao Init] 创建 Bug 失败: {result.get('message')}")
            return None

    except Exception as e:
        print(f"[Zentao Init] 创建 Bug 异常: {e}")
        return None
