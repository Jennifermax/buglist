from pydantic import BaseModel

class AIConfig(BaseModel):
    provider: str = "openai"
    api_url: str = ""
    api_key: str = ""
    model: str = "gpt-4o"

class ZentaoConfig(BaseModel):
    url: str = ""
    account: str = ""
    password: str = ""
    token: str = ""

class AppConfig(BaseModel):
    ai: AIConfig = AIConfig()
    zentao: ZentaoConfig = ZentaoConfig()
