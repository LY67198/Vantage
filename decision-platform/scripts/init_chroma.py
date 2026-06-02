from utils.chroma_client import get_collection,get_embedding_model


docs = [
    {
        "id": "doc_1",
        "text": "华东区 Q2 业绩下滑主要受渠道库存、竞品促销和重点客户采购延期影响。",
        "title": "2025-Q2华东区销售复盘",
        "source": "内部复盘/2025-Q2-华东.docx",
    },
    {
        "id": "doc_2",
        "text": "建议提高核心城市客户拜访频次，针对渠道库存较高城市设置专项去库存动作。",
        "title": "华东市场策略调整建议",
        "source": "策略文档/华东-2025.md",
    },
    {
        "id": "doc_3",
        "text": "竞品在上海、杭州推出短期价格补贴，对中小客户订单转化造成压力。",
        "title": "竞品华东区域动态分析",
        "source": "行业报告/竞品分析-2025H1.pdf",
    },
]

model = get_embedding_model()
collection = get_collection()


texts = [d["text"] for d in docs]
embeddings = model.embed_documents(texts)  # embed_documents 用 document 编码模式
collection.upsert(
    ids=[d["id"] for d in docs],
    documents=texts,
    embeddings=embeddings,
    metadatas=[{"title":d["title"],"source":d["source"]} for d in docs]
)
print(f"写入{len(docs)}个文档")

