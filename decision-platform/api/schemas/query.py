"""POST /query 请求模型。"""

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
