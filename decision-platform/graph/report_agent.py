"""Report Agent — 融合 SQL 和 RAG 结果，生成 Markdown 分析报告。"""
from graph.state import AgentState
from graph.llm import get_llm
from utils.logger import log_agent_step

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
    sql_summary = sql_result[0] if sql_result else {}
    rag_titles = [d.get("title","") for d in rag_result] if rag_result else []

    return FALLBACK_TEMPLATE.format(
            sql_summary = sql_summary if sql_summary else "数据暂时不可用",
            rag_summary = " /".jion(rag_titles) if rag_titles else "未找到相关文档",

    )


def report_agent_node(state: AgentState) -> dict:
    """融合 SQL 和 RAG 两路结果，一次 LLM 调用生成 Markdown 报告。

    前置检查：双路同时失败 → 直接返回错误提示。
    LLM 调用失败 → 内部重试 1 次 → 降级为 FALLBACK_TEMPLATE 模板拼接。
    """
    ...
    llm = get_llm()
    sql_result = state.get("sql_result",[])
    rag_result = state.get("rag_result",[])

    sql_ok = bool(sql_result) and isinstance(sql_result[0],dict) and "error" not in sql_result[0]
    rag_ok = len(rag_result) > 0

    if not sql_ok and rag_ok:
        repory = "数据库服务不可用，请稍后再试！"
        log_agent_step("RPT","双路不可用",repory)
        return{"report":repory}
        
    prompt = (
    "请基于以下 SQL 结果和 RAG 文档证据，生成一份 Markdown 分析报告。\n\n"
    "要求：\n"
    "1. 包含数据摘要表格\n"
    "2. 解释业绩变化原因\n"
    "3. 引用文档来源\n"
    f"4. 如有数据缺失，明确标注\n"
    f"\n用户问题：{state['user_query']}"
    f"\nSQL 结果：{sql_result}"
    f"\nRAG 结果：{rag_result}"
)
        
    for attempt in range(2):
        try:
            response = llm.invoke(prompt)
            report = response.content
            break
        except Exception:
            if attempt == 1:
                report = _fallback_report(sql_result,rag_result)
    log_agent_step("RPT","报告生成",report,max_len=800)

    return{"report":report}