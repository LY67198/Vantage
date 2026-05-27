"""RAG 工具 — search_docs。"""
from langchain_core.tools import tool
from mock_data.knowledge_base import SCENARIOS


@tool
def search_docs(query:str,top_k:int=3)->list[dict]:
    """检索知识库文档。"""
    docs = SCENARIOS.get("q2_east_china")
    filtered = [doc for doc in docs if doc.get("score",0) >= 0.7]
    return filtered[:top_k]


