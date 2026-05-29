"""企业智能决策中台 — 入口。"""

DEFAULT_QUERY = "Q2 华东区业绩为什么下滑？"


def main() -> None:
    """启动校验 → 构建 Graph → 交互输入 → invoke → 输出报告。"""
    ...

# 实现要点：
# 1. from mock_data import validate_scenarios
# 2. from graph.builder import build_graph
# 3. validate_scenarios() 启动校验 Mock 数据一致性
# 4. app = build_graph() 构建编译 Graph
# 5. 交互输入：user_query = input("请输入业务问题...")，空输入使用 DEFAULT_QUERY
# 6. 构造 initial_state = {"messages": [], "user_query": user_query, "sql_result": [], "rag_result": [], "report": ""}
# 7. result = app.invoke(initial_state)
# 8. 打印分隔线和 result["report"]
# 9. if __name__ == "__main__": try/except 包裹 main()，异常用 log_agent_step("ERR", ...) 记录
