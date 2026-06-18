"""查询相关 API 端点。

- POST /query: SSE 流式执行分析查询，逐步推送 Agent 执行步骤
- GET /health: 健康检查
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from graph.builder import build_graph
from graph.state import AgentState
from utils.logger import log_agent_step, set_sse_context

from api.schemas.query import QueryRequest

router = APIRouter(tags=["Query"])

# 模块级单例：首次请求时编译 graph，后续复用。
# 不要放模块级别 import 时编译 — import 时可能 DB/Redis 没启动。
_graph = None


def _get_graph():
    """返回编译好的 LangGraph 实例（懒加载单例）。"""
    global _graph
    if _graph is None:
        log_agent_step("API", "初始化", "编译 LangGraph...")
        _graph = build_graph()
    return _graph


def format_sse(event: str, data: dict) -> str:
    """格式化 SSE 消息。

    SSE 协议：event: <type>\ndata: <json>\n\n
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def event_stream(question: str, queue: asyncio.Queue, graph_task: asyncio.Task):
    """从 asyncio.Queue 读事件，格式化为 SSE 逐条 yield。

    Args:
        question: 用户原始问题
        queue: log_agent_step 推送事件的队列
        graph_task: 在线程池运行的 graph.invoke 的 Task 包装
    """
    try:
        while True:
            # task 完成且 queue 已清空 → 正常退出
            if graph_task.done() and queue.empty():
                exc = graph_task.exception()
                if exc:
                    yield format_sse("error", {"msg": str(exc)})
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.2)
                yield format_sse("agent_step", event)

                # Report Agent 完成 → 等 task 完全结束 → 退出
                if event.get("agent") == "RPT" and "完成" in event.get("status", ""):
                    if not graph_task.done():
                        await graph_task
                    break

            except asyncio.TimeoutError:
                # 超时后检查 task 是否崩溃
                if graph_task.done():
                    exc = graph_task.exception()
                    if exc:
                        yield format_sse("error", {"msg": str(exc)})
                        break
    except asyncio.CancelledError:
        yield format_sse("error", {"msg": "查询超时，请重试"})
    finally:
        yield format_sse("done", {"status": "complete"})


@router.post("/query")
async def query(request: QueryRequest, req: Request):
    """SSE 流式分析查询。

    流程：创建 asyncio.Queue → set_sse_context → graph.invoke 放线程池 →
    event_stream yield SSE 事件 → StreamingResponse 返回。

    Args:
        request: 包含用户自然语言问题的请求体。
        req: FastAPI Request 对象，用于检测客户端断开。

    Returns:
        StreamingResponse: text/event-stream 流式响应。
    """
    initial_state: AgentState = {
        "messages": [],
        "user_query": request.question,
        "sql_result": [],
        "rag_result": [],
        "report": "",
        "required_agent": [],
    }
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    # 每个请求独立的 asyncio.Queue，支持并发
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    trace_id = str(uuid.uuid4())[:8]

    # 设置 SSE 上下文，asyncio.to_thread 自动 copy_context() 传递到线程池
    set_sse_context(queue, loop, trace_id)

    graph = _get_graph()
    log_agent_step("API", "收到查询", request.question)

    # graph.invoke 同步阻塞 → 放进线程池，不阻塞 event loop；300s 兜底超时
    graph_task = asyncio.create_task(
        asyncio.wait_for(
            asyncio.to_thread(lambda: graph.invoke(initial_state, config=config)),
            timeout=300.0,
        )
    )

    return StreamingResponse(
        event_stream(request.question, queue, graph_task),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁用 nginx 缓冲
            "Connection": "keep-alive",
        },
    )


@router.get("/health")
async def health():
    """健康检查端点。"""
    return {"status": "ok"}
