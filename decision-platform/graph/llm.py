"""LLM 配置。"""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm() -> ChatOpenAI:
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
llm = get_llm()