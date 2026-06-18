"""结构化终端日志 + SSE 事件推送。"""
import contextvars
import sys
import time

# Windows GBK 终端无法输出 emoji，强制 UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESET = "\033[0m"
COLORS = {
    "ORC": "\033[95m",
    "SQL": "\033[94m",
    "RAG": "\033[92m",
    "RPT": "\033[93m",
    "SYS": "\033[96m",
    "ERR": "\033[91m",
}

# SSE 上下文：每个请求独立一份，通过 contextvars 在线程间传递
_sse_queue = contextvars.ContextVar("sse_queue", default=None)
_sse_loop = contextvars.ContextVar("sse_loop", default=None)
_trace_id = contextvars.ContextVar("trace_id", default="-")


def set_sse_context(queue, loop, trace_id: str) -> None:
    """每个请求开始时调用，后续 asyncio.to_thread 自动 copy_context() 传递。"""
    _sse_queue.set(queue)
    _sse_loop.set(loop)
    _trace_id.set(trace_id)


def log_agent_step(agent: str, status: str, content: str = "", max_len: int = 500) -> None:
    color = COLORS.get(agent, "")
    timestamp = time.strftime("%H:%M:%S")
    text = str(content)
    clipped = text[:max_len] + ("..." if len(text) > max_len else "")

    print(f"\n{'-' * 50}")
    print(f"{color}[{agent}] {timestamp} {status}{RESET}")
    if clipped:
        print(clipped)

    # --- SSE 推送（在线程池中运行时触发） ---
    try:
        q = _sse_queue.get()
        loop = _sse_loop.get()
        if q is not None and loop is not None:
            loop.call_soon_threadsafe(q.put_nowait, {
                "agent": agent,
                "status": status,
                "content": clipped,
                "trace_id": _trace_id.get(),
            })
    except Exception:
        pass  # SSE 是 best-effort，不阻塞主查询链路