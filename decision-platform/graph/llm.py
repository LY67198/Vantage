"""LLM 配置。"""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

_llm: ChatOpenAI | None = None


def _create_llm() -> ChatOpenAI:
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL", "https://api.deepseek.com")
    model = os.getenv("MODEL", "deepseek-chat")

    if not api_key:
        raise RuntimeError("缺少 API_KEY，请先在 .env 中配置 DeepSeek API Key。")

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.2,
    )


def get_llm() -> ChatOpenAI:
    """返回 ChatOpenAI 单例，首次调用时创建。"""
    global _llm
    if _llm is None:
        _llm = _create_llm()
    return _llm