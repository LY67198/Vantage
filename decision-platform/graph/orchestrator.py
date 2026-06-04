"""Orchestrator 节点 — 解析用户自然语言问题。"""

from graph.state import AgentState
from graph.llm import get_llm
from utils.logger import log_agent_step
from langchain.messages import AIMessage


def orchestrator_node(state: AgentState) -> dict:
    """解析用户自然语言问题，识别关键实体、判断所需数据源、给出分析思路。

    纯 LLM 推理，不使用工具。输出写入 messages。
    """
    ...
    llm = get_llm()
    prompt = (
        "你是企业智能决策中台的调度器。分析用户问题，判断需要哪些数据源。\n"
        "只回复 JSON，格式：{\"required_agent\": [\"sql\"]}\n\n"
        "判断规则：\n"
        "- 只问「数据/数字是多少」（营收、销量、利润、客户数、各城市/地区/品类数据）：只返回 [\"sql\"]\n"
        "- 只问「原因/策略/建议/文档/怎么做」（业绩为什么下滑、有什么策略建议、某事件的复盘分析）：只返回 [\"rag\"]\n"
        "- 同时问数据和原因（例如「Q2 业绩为什么下滑」既要数据又要原因）：返回 [\"sql\", \"rag\"]\n\n"
        "示例：\n"
        "- 「华东区各城市营收是多少」→ [\"sql\"]\n"
        "- 「华东区有哪些策略建议」→ [\"rag\"]\n"
        "- 「华东区 Q2 业绩为什么下滑」→ [\"sql\", \"rag\"]\n\n"
        f"用户问题：{state['user_query']}"
    )
    response = llm.invoke(prompt)

    try:
        import json,re
        match = re.search(r'\{.*\}',response.content,re.DOTALL)
        data = json.loads(match.group())
        required = data.get("required_agent",["sql","rag"])
    
    except Exception:
        required = ["sql","rag"]


    log_agent_step("ORC", "🔍 路由决策", f"触发: {required}")

    return{
        "messages":[AIMessage(content=response.content)],
        "required_agent":required
    }


