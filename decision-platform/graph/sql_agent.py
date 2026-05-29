"""SQL Agent — 手写 ReAct 循环查询销售数据。"""

from graph.state import AgentState

MAX_ITERATIONS = 3


def sql_agent_node(state: AgentState) -> dict:
    """手写 ReAct 循环：LLM 生成 SQL → execute_query → 观察结果 → 判断是否足够。

    输出格式：
        {"region": "华东", "period": "2025-Q2", "revenue": 2340,
         "yoy_change": -12.3, "raw_rows": [...], "sql_executed": "SELECT ..."}
    失败时返回 {"error": str}，下游 Report Agent 可据此标注。
    """
    ...

# 实现要点：
# 1. from graph.llm import get_llm; llm = get_llm()
# 2. from tools.sql_tools import execute_query
# 3. llm.bind_tools([execute_query]) 绑定工具
# 4. 构造 HumanMessage 作为 system prompt + user_query
# 5. ReAct 循环 (max MAX_ITERATIONS 轮):
#    a. llm_with_tools.invoke(messages)
#    b. 如果无 tool_calls → 第一轮说明 LLM 无法生成 SQL，返回 error；后续轮说明推理完成
#    c. 有 tool_calls → 调用 execute_query.invoke(tool_args)
#    d. 将 ToolMessage 追加到 messages
#    e. 如果 result 无 error → 返回 {"sql_result": [result], "messages": messages}
#    f. 有 error → 继续下一轮让 LLM 修正
# 6. 耗尽迭代返回 {"sql_result": [{"error": "..."}], "messages": messages}
# 7. 每步用 log_agent_step("SQL", ...) 记录日志
#
# 注意：tool_calls 元素的访问方式取决于 langchain-core 版本：
#   当前版本 (1.4.0) 返回 list[dict]，用 tool_call["name"] / tool_call["args"] / tool_call["id"]
#   升级前需验证版本兼容性
