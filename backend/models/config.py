from pydantic import BaseModel

class AIConfig(BaseModel):
    api_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-5.4"

class ZentaoConfig(BaseModel):
    url: str = ""
    account: str = ""
    password: str = ""
    token: str = ""

class AppConfig(BaseModel):
    ai: AIConfig = AIConfig()
    zentao: ZentaoConfig = ZentaoConfig()
