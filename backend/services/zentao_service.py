import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from ..models.config import ZentaoConfig

MAX_BUG_ATTACHMENT_BYTES = 8 * 1024 * 1024

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

    def _parse_file_upload_response(self, response: httpx.Response) -> Optional[Dict[str, Any]]:
        """若响应为 JSON 且表示成功则返回 payload，否则返回 None（表示本次策略失败）。"""
        text = (response.text or "").strip()
        if not text or text.startswith("<"):
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        if not isinstance(payload, dict):
            return payload if payload else None
        if payload.get("error"):
            return None
        if payload.get("status") == "fail":
            return None
        # 成功：常见字段 status / id / url
        if payload.get("status") == "success" or payload.get("id") is not None:
            return payload
        if "id" in payload and payload.get("id"):
            return payload
        return None

    async def upload_bug_file(
        self,
        bug_id: int,
        file_content: bytes,
        filename: str = "screenshot.png",
        content_type: str = "image/png",
    ) -> Dict[str, Any]:
        """
        上传附件到已存在的 Bug。
        禅道/禅道云不同版本路由差异较大，依次尝试多种端点与表单字段（官方文档为 v2/files + token + multipart）。
        """
        if not self.token:
            return {"success": False, "message": "未配置 Token，无法上传附件"}
        if not file_content:
            return {"success": False, "message": "文件内容为空"}

        safe_name = (filename or "screenshot.png").replace("/", "_").replace("\\", "_")[:120]
        file_tuple = (safe_name, file_content, content_type)
        bid_str = str(int(bug_id))
        last_detail = ""

        # (url, headers, files_dict, data_dict) — 注意 multipart 请求不要带 Content-Type: application/json
        attempts: List[tuple] = []

        def hdr_token_lower() -> Dict[str, str]:
            h: Dict[str, str] = {"token": self.token}
            if self.account:
                h["zentao"] = self.account
            return h

        def hdr_token_upper() -> Dict[str, str]:
            h: Dict[str, str] = {"Token": self.token}
            if self.account:
                h["zentao"] = self.account
            return h

        def hdr_token_lower_only() -> Dict[str, str]:
            return {"token": self.token}

        # 1) v2/files — file 字段（官方文档）
        for hdr_fn in (hdr_token_lower, hdr_token_upper, hdr_token_lower_only):
            attempts.append((
                f"{self.base_url}/api.php/v2/files",
                hdr_fn(),
                {"file": file_tuple},
                {"objectType": "bug", "objectID": bid_str},
            ))
            attempts.append((
                f"{self.base_url}/api.php/v2/files",
                hdr_fn(),
                {"file": file_tuple},
                {"objectType": "bug", "objectID": bug_id},
            ))

        # 2) 社区常见：files[] 字段名
        attempts.append((
            f"{self.base_url}/api.php/v2/files",
            hdr_token_lower(),
            {"files[]": file_tuple},
            {"objectType": "bug", "objectID": bid_str},
        ))

        # 3) Token 放 Query（部分环境只认 URL token）
        attempts.append((
            f"{self.base_url}/api.php/v2/files?token={self.token}",
            hdr_token_lower_only(),
            {"file": file_tuple},
            {"objectType": "bug", "objectID": bid_str},
        ))

        # 4) v1/files（少数部署与开源版路由）
        attempts.append((
            f"{self.base_url}/api.php/v1/files",
            hdr_token_lower(),
            {"file": file_tuple},
            {"objectType": "bug", "objectID": bid_str},
        ))
        attempts.append((
            f"{self.base_url}/api.php/v1/files?token={self.token}",
            {},
            {"file": file_tuple},
            {"objectType": "bug", "objectID": bid_str},
        ))

        for url, headers, files, data in attempts:
            try:
                response = await self.client.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60.0,
                )
            except Exception as exc:
                last_detail = str(exc)[:200]
                continue

            if response.status_code not in (200, 201):
                last_detail = f"HTTP {response.status_code}"
                continue

            parsed = self._parse_file_upload_response(response)
            if parsed is not None:
                return {"success": True, "data": parsed, "method": url.split("?")[0].rsplit("/", 1)[-1]}

            last_detail = (response.text or "")[:220]

        return {
            "success": False,
            "message": f"附件上传失败（已尝试多种禅道接口方式）。最后响应片段：{last_detail or '无响应'}",
        }

    async def fetch_screenshot_bytes(
        self,
        raw_url: str,
        artifact_base_url: str = "",
        project_root: Optional[Path] = None,
    ) -> Tuple[Optional[bytes], str, str]:
        """
        解析截图地址并读取字节。返回 (bytes|None, filename, content_type)
        """
        raw = (raw_url or "").strip()
        if not raw:
            return None, "screenshot.png", "image/png"

        name = Path(raw.split("?")[0]).name or "screenshot.png"
        if not name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            name = f"{name}.png"

        # 绝对 URL
        if raw.startswith(("http://", "https://")):
            try:
                r = await self.client.get(raw, timeout=30.0, follow_redirects=True)
                if r.status_code == 200 and r.content:
                    if len(r.content) > MAX_BUG_ATTACHMENT_BYTES:
                        return None, name, "image/png"
                    ct = r.headers.get("content-type", "").split(";")[0].strip() or "image/png"
                    return r.content, name, ct if ct.startswith("image/") else "image/png"
            except Exception:
                pass

        # 相对路径：先拼 artifact_base_url，再尝试本地 artifacts
        if raw.startswith("/"):
            base = (artifact_base_url or "").strip().rstrip("/")
            if base:
                try:
                    r = await self.client.get(f"{base}{raw}", timeout=30.0, follow_redirects=True)
                    if r.status_code == 200 and r.content:
                        if len(r.content) > MAX_BUG_ATTACHMENT_BYTES:
                            return None, name, "image/png"
                        return r.content, name, "image/png"
                except Exception:
                    pass
            if project_root is not None:
                local = project_root / raw.lstrip("/")
                try:
                    if local.is_file():
                        data = local.read_bytes()
                        if len(data) <= MAX_BUG_ATTACHMENT_BYTES:
                            return data, name, "image/png"
                except Exception:
                    pass

        return None, name, "image/png"

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
