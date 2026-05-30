"""企业智能决策中台 — 入口。"""

from graph.builder import build_graph
from mock_data import validate_scenarios
from utils.logger import log_agent_step

DEFAULT_QUERY = "Q2 华东区业绩为什么下滑？"


def main() -> None:
    validate_scenarios()
    app = build_graph()

    user_query = input(f"请输入业务问题（默认：{DEFAULT_QUERY}）：").strip()
    if not user_query:
        user_query = DEFAULT_QUERY

    initial_state = {
        "messages": [],
        "user_query": user_query,
        "sql_result": [],
        "rag_result": [],
        "report": "",
    }

    result = app.invoke(initial_state)

    print("\n" + "=" * 60)
    print(result["report"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_agent_step("ERR", "运行失败", str(exc))
        raise