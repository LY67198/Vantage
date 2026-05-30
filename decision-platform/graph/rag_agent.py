"""RAG Agent — 手写 ReAct 循环检索文档知识库。"""

from graph.state import AgentState
from tools.rag_tools import search_docs
from graph.llm import get_llm
from langchain.messages import HumanMessage,ToolMessage
from utils.logger import log_agent_step

MAX_ITERATIONS = 3


def rag_agent_node(state: AgentState) -> dict:
    """手写 ReAct 循环：LLM 生成检索关键词 → search_docs → 观察结果 → 判断是否需要更多。

    输出格式：
        [{"title": "...", "content": "...", "source": "...", "score": 0.92}, ...]
    无结果时返回 []，下游 Report Agent 可据此标注「未找到相关文档」。
    """
    ...
    llm = get_llm()
    llm_with_tool = llm.bind_tools([search_docs])
    messages = [
    HumanMessage(
        content=(
            "你是 RAG Agent，负责从企业知识库检索相关文档。"
            "根据用户问题生成检索关键词，调用 search_docs 工具。"
            "检索后判断是否需要更换关键词再搜，直到收集到足够证据。"
            f"\n\n用户问题：{state['user_query']}"
        )
    )
]   
    log_agent_step("RAG","RAG开始工作",state["user_query"])
    collected_docs = []

    for i in range(MAX_ITERATIONS):
        response = llm_with_tool.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            content = response.content if hasattr(response,"content") else str(response)
            log_agent_step("rag"," 检索未完成",content[:300])
            if i == 0:

                log_agent_step("rag","未生成查询",content[:300])
                return {"rag_result": [{"error": "LLM 未生成工具调用", "raw_output": content}], "messages": messages}
            log_agent_step("rag","检索完成",content[:300])
            break
    
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name")
            if tool_name != "search_docs":
                continue
            tool_args = tool_call.get("args",{})
            rag_text = tool_args.get("RAG","") 
            log_agent_step("rag","检索",rag_text[:200])

            docs = search_docs.invoke(tool_args)
            collected_docs.extend(docs)

            messages.append(
                ToolMessage(
                    content=str(docs),tool_call_id = tool_call["id"]
                )
            )
            if docs:
                title = [d["title"] for d in docs]
                log_agent_step(
                    "RAG","检索成功",
                    f"找到{len(docs)}份文档:{title}"
                )

                return {"rag_result":collected_docs,"messages":messages}
            log_agent_step("RAG","未命中","score>= 0,7的文档数为 0")

    log_agent_step("RAG","达到最大迭代",f"已查询{MAX_ITERATIONS}次")
    return {"rag_result":collected_docs,"messages":messages}


