"""RAG 工具 — search_docs。"""
from langchain_core.tools import tool
from utils.chroma_client import get_collection,get_embedding_model



@tool
def search_docs(query:str,top_k:int=3)->list[dict]:
    """检索知识库文档。"""
    model = get_embedding_model()
    collection = get_collection()

    query_embedding = model.embed_query(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        score = round(1 - dist, 4)
        if score >= 0.7:
            docs.append({
                "title": meta.get("title", ""),
                "content": doc,
                "source": meta.get("source", ""),
                "score": score,
            })

    return docs

