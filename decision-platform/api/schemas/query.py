"""POST /query 请求/响应模型。"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """用户查询请求。

    Attributes:
        question: 用户输入的自然语言问题，如「Q2 华东区业绩为什么下滑？」
    """
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户自然语言问题",
        examples=["Q2 华东区业绩为什么下滑？"],
    )


class QueryResponse(BaseModel):
    """查询分析结果。

    Attributes:
        report: Report Agent 生成的 Markdown 分析报告（含数据表格 + 文档引用）
        sql_result: SQL Agent 查询的结构化数据（columns + rows）
        rag_result: RAG Agent 检索到的相关文档列表
    """
    report: str = Field(..., description="Markdown 格式分析报告")
    sql_result: list = Field(default_factory=list, description="SQL Agent 查询结果")
    rag_result: list = Field(default_factory=list, description="RAG Agent 检索结果")
