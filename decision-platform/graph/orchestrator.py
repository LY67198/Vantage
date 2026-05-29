"""Orchestrator 节点 — 解析用户自然语言问题。"""

from graph.state import AgentState


def orchestrator_node(state: AgentState) -> dict:
    """解析用户自然语言问题，识别关键实体、判断所需数据源、给出分析思路。

    纯 LLM 推理，不使用工具。输出写入 messages。
    """
    ...

# 实现要点：
# 1. from graph.llm import get_llm — 使用懒加载，首次调用时创建
# 2. 从 state["user_query"] 获取用户问题
# 3. 构造 prompt，要求 LLM 识别实体（区域、时间段、指标类型）、判断数据源、给出分析思路
# 4. llm = get_llm(); response = llm.invoke(prompt)
# 5. 用 log_agent_step("ORC", ...) 记录日志
# 6. 返回 {"messages": [AIMessage(content=response.content)]}
