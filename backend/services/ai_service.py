from openai import AsyncOpenAI
import base64
from typing import Dict, Any

class AIService:
    def __init__(self, api_url: str, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_url or None)
        self.model = model

    async def generate_testcases(self, document_content: str) -> list:
        prompt = f"""根据以下产品文档，生成测试用例。
每个测试用例需要包含：
- name: 用例名称
- precondition: 前置条件
- steps: 测试步骤数组，每个步骤包含 action, description, value

支持的 action 类型：
- 打开页面：导航到 URL，value 为 URL
- 输入：输入文本，description 描述操作，value 为输入内容
- 点击：点击元素，description 描述点击什么
- 等待：等待指定时间，value 为秒数
- 验证：AI 视觉对比验证，description 描述预期结果

请返回 JSON 数组格式的测试用例。
不要返回任何解释，只返回 JSON。

产品文档：
{document_content}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        content = response.choices[0].message.content
        import json
        try:
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except:
            return []
        return []

    async def analyze_screenshot(self, image_data: bytes, description: str) -> Dict[str, Any]:
        """使用视觉模型分析截图"""
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        prompt = f"""请分析这张截图，判断是否符合以下预期描述：
"{description}"

请返回 JSON 格式：
{{
  "passed": true 或 false,
  "reason": "判断原因"
}}
只返回 JSON，不要返回其他内容。"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                    ]
                }
            ]
        )

        content = response.choices[0].message.content
        import json
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except:
            return {"passed": False, "reason": "解析失败"}
        return {"passed": False, "reason": "解析失败"}
