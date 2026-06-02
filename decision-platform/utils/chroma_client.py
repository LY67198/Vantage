from langchain_community.embeddings import DashScopeEmbeddings
import chromadb
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_project_root = Path(__file__).resolve().parent.parent  # utils/ → decision-platform/
_client = None
_model = None


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(_project_root / "chroma_data"))
    return _client

def get_embedding_model():
    global _model
    if _model is None:
        _model = DashScopeEmbeddings(
            dashscope_api_key=os.getenv("EMBEDDING_API_KEY"),
            model=os.getenv("MODEL_NAME")
        )
    return _model

def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="vantage_docs",
        metadata={"hnsw:space": "cosine"}
    )



    

