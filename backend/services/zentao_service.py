import httpx
from typing import Optional, Dict, Any, List
from ..models.config import ZentaoConfig

class ZentaoService:
    def __init__(self, config: ZentaoConfig):
        self.config = config
        self.base_url = config.url.rstrip('/')
        self.account = config.account
        self.token = config.token
        self.client = httpx.AsyncClient(timeout=60.0, verify=False)

    def _get_headers(self) -> Dict[str, str]:
        """获取禅道 API 请求头"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Token"] = self.token
        if self.account:
            headers["zentao"] = self.account
        return headers

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()

    async def get_token_by_password(self, password: str) -> Dict[str, Any]:
        """通过账号密码获取 Token"""
        try:
            if not self.account:
                return {"success": False, "message": "请提供账号"}
            response = await self.client.post(
                f"{self.base_url}/api.php/v1/tokens",
                json={"account": self.account, "password": password}
            )
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    if "token" in data:
                        self.token = data["token"]
                        return {"success": True, "token": data["token"]}
                    return {"success": False, "message": data.get("error", "获取 Token 失败")}
                except:
                    return {"success": False, "message": f"Token 响应解析失败: {response.text}"}
            else:
                try:
                    error_data = response.json() if response.content else {}
                    return {"success": False, "message": error_data.get("error", f"获取 Token 失败: {response.status_code}")}
                except:
                    return {"success": False, "message": f"获取 Token 失败: {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"获取 Token 错误: {str(e)}"}

    async def test_connection(self) -> Dict[str, Any]:
        """测试禅道连接"""
        try:
            headers = self._get_headers()
            response = await self.client.get(
                f"{self.base_url}/api.php/v1/products",
                headers=headers
            )
            if response.status_code == 200:
                return {"success": True, "message": "连接成功"}
            elif response.status_code == 401:
                return {"success": False, "message": "认证失败，请检查账号和 Token"}
            else:
                return {"success": False, "message": f"连接失败: {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"连接错误: {str(e)}"}

    async def get_products(self) -> Dict[str, Any]:
        """获取产品列表"""
        try:
            headers = self._get_headers()
            response = await self.client.get(
                f"{self.base_url}/api.php/v1/products",
                headers=headers
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                    # 禅道返回格式可能是 {page, total, limit, products: []}
                    if isinstance(data, dict):
                        return {"success": True, "data": data.get("products", [])}
                    return {"success": True, "data": data if isinstance(data, list) else []}
                except:
                    # 如果不是 JSON 格式，直接返回文本
                    return {"success": True, "data": [], "raw": response.text}
            else:
                return {"success": False, "message": f"获取产品失败: {response.status_code}", "data": []}
        except Exception as e:
            return {"success": False, "message": f"获取产品错误: {str(e)}", "data": []}

    async def get_product(self, product_id: int) -> Dict[str, Any]:
        """获取单个产品详情"""
        try:
            headers = self._get_headers()
            response = await self.client.get(
                f"{self.base_url}/api.php/v1/products/{product_id}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "data": data}
            else:
                return {"success": False, "message": f"获取产品详情失败: {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"获取产品详情错误: {str(e)}"}

    async def get_bugs(self, product_id: Optional[int] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """获取 Bug 列表"""
        try:
            headers = self._get_headers()
            url = f"{self.base_url}/api.php/v1/bugs"
            params = []
            if product_id:
                params.append(f"product={product_id}")
            if status:
                params.append(f"status={status}")
            if params:
                url += "?" + "&".join(params)

            response = await self.client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                # 禅道返回格式可能是 {page, total, bugs: []}
                if isinstance(data, dict):
                    return {"success": True, "data": data.get("bugs", [])}
                return {"success": True, "data": data if isinstance(data, list) else []}
            else:
                error_data = response.json() if response.content else {}
                return {"success": False, "message": error_data.get("error", f"获取Bug列表失败: {response.status_code}"), "data": []}
        except Exception as e:
            return {"success": False, "message": f"获取Bug列表错误: {str(e)}", "data": []}

    async def create_bug(self, bug_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建 Bug"""
        try:
            headers = self._get_headers()
            # 确保必填字段存在
            if "product" not in bug_data and "productID" not in bug_data:
                return {"success": False, "message": "缺少产品ID (product)"}
            if "title" not in bug_data or not bug_data["title"]:
                return {"success": False, "message": "缺少标题 (title)"}

            # 从 bug_data 中提取 product 参数用于 URL
            product = bug_data.get("product") or bug_data.get("productID", 1)

            # 构建请求体，设置默认值
            request_body = {
                "product": product,
                "title": bug_data["title"],
                "pri": bug_data.get("pri", 3),
                "severity": bug_data.get("severity", 3),
                "type": bug_data.get("type", "codeerror"),
                "openedBuild": bug_data.get("openedBuild", "trunk"),
            }
            # 添加可选字段
            if "steps" in bug_data:
                request_body["steps"] = bug_data["steps"]
            if "expectedResult" in bug_data:
                request_body["expectedResult"] = bug_data["expectedResult"]
            if "assignedTo" in bug_data:
                request_body["assignedTo"] = bug_data["assignedTo"]
            if "module" in bug_data:
                request_body["module"] = bug_data["module"]
            if "os" in bug_data:
                request_body["os"] = bug_data["os"]
            if "browser" in bug_data:
                request_body["browser"] = bug_data["browser"]

            response = await self.client.post(
                f"{self.base_url}/api.php/v1/bugs?product={product}",
                headers=headers,
                json=request_body
            )
            if response.status_code in [200, 201]:
                data = response.json()
                if "error" in data:
                    return {"success": False, "message": data["error"]}
                return {"success": True, "data": data}
            else:
                error_data = response.json() if response.content else {}
                return {"success": False, "message": error_data.get("error", f"创建Bug失败: {response.status_code}")}
        except Exception as e:
            return {"success": False, "message": f"创建Bug错误: {str(e)}"}

    async def get_product_modules(self, product_id: int) -> Dict[str, Any]:
        """获取产品的模块列表"""
        try:
            headers = self._get_headers()
            response = await self.client.get(
                f"{self.base_url}/api.php/v1/modules?product={product_id}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "data": data if isinstance(data, list) else data.get("data", [])}
            else:
                return {"success": False, "message": f"获取模块失败: {response.status_code}", "data": []}
        except Exception as e:
            return {"success": False, "message": f"获取模块错误: {str(e)}", "data": []}

    async def get_users(self) -> Dict[str, Any]:
        """获取用户列表"""
        try:
            headers = self._get_headers()
            response = await self.client.get(
                f"{self.base_url}/api.php/v1/users",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "data": data if isinstance(data, list) else data.get("data", [])}
            else:
                return {"success": False, "message": f"获取用户失败: {response.status_code}", "data": []}
        except Exception as e:
            return {"success": False, "message": f"获取用户错误: {str(e)}", "data": []}

    async def get_product_builds(self, product_id: int) -> Dict[str, Any]:
        """获取产品的版本/构建列表"""
        try:
            headers = self._get_headers()
            response = await self.client.get(
                f"{self.base_url}/api.php/v1/builds?productID={product_id}",
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "data": data if isinstance(data, list) else data.get("data", [])}
            else:
                return {"success": False, "message": f"获取版本失败: {response.status_code}", "data": []}
        except Exception as e:
            return {"success": False, "message": f"获取版本错误: {str(e)}", "data": []}


def get_zentao_service(config: ZentaoConfig) -> ZentaoService:
    """获取禅道服务实例"""
    return ZentaoService(config)
