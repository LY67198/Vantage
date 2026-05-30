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
    "你是企业智能决策中台的调度器。请分析以下用户问题：\n"
    "1. 识别关键实体（区域、时间段、指标类型等）\n"
    "2. 判断需要哪些数据源（销售数据 / 文档知识库 / 两者都需要）\n"
    "3. 给出分析思路\n"
    f"\n用户问题：{state['user_query']}"
)
    response = llm.invoke(prompt)

    log_agent_step("ORC","🔍 分析完成",response.content)

    return{"messages":[AIMessage(content=response.content)]}


