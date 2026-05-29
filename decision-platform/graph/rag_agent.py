"""RAG Agent — 手写 ReAct 循环检索文档知识库。"""

from graph.state import AgentState

MAX_ITERATIONS = 3


def rag_agent_node(state: AgentState) -> dict:
    """手写 ReAct 循环：LLM 生成检索关键词 → search_docs → 观察结果 → 判断是否需要更多。

    输出格式：
        [{"title": "...", "content": "...", "source": "...", "score": 0.92}, ...]
    无结果时返回 []，下游 Report Agent 可据此标注「未找到相关文档」。
    """
    ...

# 实现要点：
# 1. from graph.llm import get_llm; llm = get_llm()
# 2. from tools.rag_tools import search_docs
# 3. llm.bind_tools([search_docs]) 绑定工具
# 4. 构造 HumanMessage 作为 system prompt + user_query
# 5. collected_docs = [] 用于累积文档（用 extend 而非覆盖）
# 6. ReAct 循环 (max MAX_ITERATIONS 轮):
#    a. llm_with_tools.invoke(messages)
#    b. 如果无 tool_calls → 第一轮说明未生成检索，返回 []；后续轮说明检索完成
#    c. 有 tool_calls → 调用 search_docs.invoke(tool_args)
#    d. 将 ToolMessage 追加到 messages
#    e. 如果 docs 非空 → 返回 {"rag_result": collected_docs, "messages": messages}（用 collected_docs 而非 docs，保持累积语义一致）
#    f. 为空 → 继续下一轮让 LLM 换关键词
# 7. 耗尽迭代返回 {"rag_result": collected_docs, "messages": messages}
# 8. 每步用 log_agent_step("RAG", ...) 记录日志
#
# 注意：tool_calls 元素的访问方式取决于 langchain-core 版本：
#   当前版本 (1.4.0) 返回 list[dict]，用 tool_call["name"] / tool_call["args"] / tool_call["id"]
#   升级前需验证版本兼容性
