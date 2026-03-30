import os


DEFAULT_BASE_URL = "https://beta-5.bydtms.com/zh"


def get_base_url() -> str:
    return os.getenv("BUGLIST_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
