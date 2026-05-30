"""Graph 构建器 — 组装 Orchestrator → SQL/RAG 并行 → Report 流程图。"""

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send
from graph.sql_agent import sql_agent_node
from graph.rag_agent import rag_agent_node
from graph.report_agent import report_agent_node
from graph.orchestrator import orchestrator_node

from graph.state import AgentState

retry_policy = RetryPolicy(
    max_attempts=3,
    initial_interval=0.5,
    backoff_factor=2.0,
)


def dispatch_workers(state: AgentState) -> list[Send]:
    """Phase 1 默认 SQL/RAG 全并行分发。

    Phase 2 替换为条件路由：根据 orchestrator 输出动态决定启动哪些 Agent。
    """
    ...
    return[
        Send("sql_agent",state),
        Send("rag_agent",state),
    ]

def build_graph():
    """构建 StateGraph，组装 4 个节点并配置 Send API 并行 + join 语义。

    返回 compiled graph，可直接 app.invoke(initial_state)。
    """
    ...
    workflow = StateGraph(AgentState)
    workflow.add_node("Orchestrator",orchestrator_node,retry_policy=retry_policy)
    workflow.add_node("sql_agent",sql_agent_node,retry_policy=retry_policy)
    workflow.add_node("rag_agent",rag_agent_node,retry_policy=retry_policy)
    workflow.add_node("report_agent",report_agent_node,retry_policy=retry_policy)

    workflow.add_edge(START,"Orchestrator")
    workflow.add_conditional_edges( "Orchestrator",dispatch_workers)
    workflow.add_edge(["sql_agent","rag_agent"],"report_agent")
    workflow.add_edge("report_agent",END)

    return workflow.compile()



