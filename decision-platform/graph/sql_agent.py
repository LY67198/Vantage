"""SQL Agent — 手写 ReAct 循环查询销售数据。"""
from graph.state import AgentState
from graph.llm import get_llm
from tools.sql_tools import execute_query
from langchain_core.messages import HumanMessage, ToolMessage
from utils.logger import log_agent_step


MAX_ITERATIONS = 3


def sql_agent_node(state: AgentState) -> dict:
    """手写 ReAct 循环：LLM 生成 SQL → execute_query → 观察结果 → 判断是否足够。

    输出格式：
        {"region": "华东", "period": "2025-Q2", "revenue": 2340,
         "yoy_change": -12.3, "raw_rows": [...], "sql_executed": "SELECT ..."}
    失败时返回 {"error": str}，下游 Report Agent 可据此标注。
    """
    llm = get_llm()
    llm_with_tool = llm.bind_tools([execute_query])
    messages = [
        HumanMessage(
            content=(
                "你是 SQL Agent，负责查询企业销售数据。"
                "根据用户问题生成 SQL 查询并调用 execute_query 工具。"
                "查询结果返回后，判断数据是否足够回答用户问题，不够则调整 SQL 再查。"
                f"\n\n用户问题：{state['user_query']}"
            )
        )
    ]

    log_agent_step("SQL", "⚡ 开始推理", state["user_query"])

    for i in range(MAX_ITERATIONS):
        response = llm_with_tool.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            # 本轮无工具调用，记录原因并退出
            content = response.content if hasattr(response, "content") else str(response)
            log_agent_step("SQL", "❌ 未生成查询", content[:300])
            if i == 0:
                # 第一轮就不调工具：LLM 无法生成 SQL
                log_agent_step("SQL", "⚠️ 未生成查询", content[:300])
                return {
                    "sql_result": [{"error": "LLM 未生成工具调用", "raw_output": content}],
                    "messages": messages,
                }
            log_agent_step("sql","✅推理完成",content[:300])
            break

        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name")
            if tool_name != "execute_query":
                continue

            tool_args = tool_call.get("args", {})
            sql_text = tool_args.get("sql", "")
            log_agent_step("SQL", "⚡ 执行查询", sql_text[:200])

            result = execute_query.invoke(tool_args)
            messages.append(ToolMessage(
                content=str(result), tool_call_id=tool_call["id"]
            ))

            if "error" not in result:
                log_agent_step(
                    "SQL",
                    "✅ 查询完成",
                    f"region={result.get('region')}, "
                    f"revenue={result.get('revenue')}万, "
                    f"yoy={result.get('yoy_change')}%",
                )
                return {"sql_result": [result], "messages": messages}

            # 查询返回了 error，记录并继续下一轮
            log_agent_step("SQL", "⚠️ 查询返回错误", str(result)[:300])

    log_agent_step("SQL", "⚠️ 达最大迭代", f"已轮询 {MAX_ITERATIONS} 次")
    return {
        "sql_result": [{"error": f"已达最大迭代次数 {MAX_ITERATIONS}，未查询到有效结果"}],
        "messages": messages,
    }
