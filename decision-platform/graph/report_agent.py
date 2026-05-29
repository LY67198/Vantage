"""Report Agent — 融合 SQL 和 RAG 结果，生成 Markdown 分析报告。"""

from graph.state import AgentState

FALLBACK_TEMPLATE = """## 分析报告（降级模式）

### 数据摘要
{sql_summary}

### 文档证据
{rag_summary}

> 报告生成服务暂时异常，以上为原始结果摘要。
"""


def _fallback_report(sql_result: list, rag_result: list) -> str:
    """LLM 调用失败时的降级模板拼接，保证始终有输出。"""
    ...


def report_agent_node(state: AgentState) -> dict:
    """融合 SQL 和 RAG 两路结果，一次 LLM 调用生成 Markdown 报告。

    前置检查：双路同时失败 → 直接返回错误提示。
    LLM 调用失败 → 内部重试 1 次 → 降级为 FALLBACK_TEMPLATE 模板拼接。
    """
    ...

# 实现要点：
# 1. from graph.llm import get_llm; llm = get_llm()
# 2. 从 state 获取 sql_result 和 rag_result（用 .get() 防御性取值）
# 3. sql_ok = bool(sql_result) and isinstance(sql_result[0], dict) and "error" not in sql_result[0]
#    （用 isinstance 防止空 dict 误判，不用 (sql_result[0] or {}) 这种脆弱写法）
# 4. rag_ok = len(rag_result) > 0
# 5. 前置检查：if not sql_ok and not rag_ok → 返回 "⚠️ 数据服务暂时不可用..."
# 6. 构造 prompt，融合用户问题 + SQL 结果 + RAG 结果，要求生成 Markdown 报告
# 7. LLM 调用做 2 次尝试（内部重试，不依赖 RetryPolicy）：
#    for attempt in range(2):
#        try: response = llm.invoke(prompt); report = response.content; break
#        except Exception:
#            if attempt == 1: report = _fallback_report(sql_result, rag_result)
# 8. _fallback_report 中不要直接把 list 拼进字符串，提取结构化字段后再 format
# 9. log_agent_step("RPT", ...) 记录日志
# 10. 返回 {"report": report}
#
# 注意：RetryPolicy 绑定在 report_agent 上不会生效（内部 try/except 吃掉了异常），
# 这是有意为之 — 降级兜底优先于无限重试。如后续需要 RetryPolicy 接管，去掉内部 try/except。
