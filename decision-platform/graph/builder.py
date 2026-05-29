"""Graph 构建器 — 组装 Orchestrator → SQL/RAG 并行 → Report 流程图。"""

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send

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


def build_graph():
    """构建 StateGraph，组装 4 个节点并配置 Send API 并行 + join 语义。

    返回 compiled graph，可直接 app.invoke(initial_state)。
    """
    ...

# 实现要点：
# 1. workflow = StateGraph(AgentState)
# 2. 添加 4 个节点（均绑定 retry_policy）:
#    workflow.add_node("orchestrator", orchestrator_node, retry_policy=retry_policy)
#    workflow.add_node("sql_agent", sql_agent_node, retry_policy=retry_policy)
#    workflow.add_node("rag_agent", rag_agent_node, retry_policy=retry_policy)
#    workflow.add_node("report_agent", report_agent_node, retry_policy=retry_policy)
# 3. 连线：
#    workflow.add_edge(START, "orchestrator")
#    workflow.add_conditional_edges("orchestrator", dispatch_workers)
#    workflow.add_edge(["sql_agent", "rag_agent"], "report_agent")  # list 语法已验证支持
#    workflow.add_edge("report_agent", END)
# 4. return workflow.compile()
#
# dispatch_workers 实现：
#   return [Send("sql_agent", state), Send("rag_agent", state)]
