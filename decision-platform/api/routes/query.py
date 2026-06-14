"""查询相关 API 端点。

- POST /query: 执行分析查询，同步返回 report + sql_result + rag_result
- GET /health: 健康检查
"""

import uuid

from fastapi import APIRouter, HTTPException
from graph.builder import build_graph
from graph.state import AgentState
from utils.logger import log_agent_step

from api.schemas.query import QueryRequest, QueryResponse

router = APIRouter(tags=["Query"])

# 模块级单例：首次请求时编译 graph，后续复用。
# 不要放模块级别 import 时编译 — import 时可能 DB/Redis 没启动。
_graph = None


def _get_graph():
    """返回编译好的 LangGraph 实例（懒加载单例）。

    Returns:
        CompiledStateGraph: build_graph() 返回的 compiled graph。
    """
    global _graph
    if _graph is None:
        log_agent_step("API", "初始化", "编译 LangGraph...")
        _graph = build_graph()
    return _graph


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """执行分析查询。

    流程：接收用户问题 → 构建 AgentState → graph.ainvoke → 返回报告。

    Args:
        request: 包含用户自然语言问题的请求体。

    Returns:
        QueryResponse: report（Markdown）+ sql_result + rag_result。

    Raises:
        HTTPException 500: graph 执行异常或 LLM 调用失败。
    """
    try:
        initial_state: AgentState = {
            "messages": [],
            "user_query": request.question,
            "sql_result": [],
            "rag_result": [],
            "report": "",
            "required_agent": [],
        }
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        graph = _get_graph()

        log_agent_step("API", "收到查询", request.question)
        result = await graph.ainvoke(initial_state, config=config)

        return QueryResponse(
            report=result.get("report", ""),
            sql_result=result.get("sql_result", []),
            rag_result=result.get("rag_result", []),
        )
    except Exception as exc:
        log_agent_step("API", "查询失败", str(exc))
        raise HTTPException(status_code=500, detail=f"分析查询失败: {str(exc)}") from exc


@router.get("/health")
async def health():
    """健康检查端点。

    Returns:
        dict: {"status": "ok"} 表示服务正常运行。
    """
    return {"status": "ok"}
