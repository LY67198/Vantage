"""企业智能决策中台 — 入口。"""

import uuid
from graph.builder import build_graph
from utils.logger import log_agent_step

DEFAULT_QUERY = "Q2 华东区业绩为1什么下滑？"


def main() -> None:
    app = build_graph()

    print("输入 exit 退出")
    while True:
        user_query = input("\n请输入问题：").strip()
        if user_query.lower() == "exit":
            break
        if not user_query:
            user_query = DEFAULT_QUERY

        initial_state = {
            "messages": [],
            "user_query": user_query,
            "sql_result": [],
            "rag_result": [],
            "report": "",
            "required_agent": [],
        }

        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        result = app.invoke(initial_state, config=config)
        print("\n" + "=" * 60)
        print(result["report"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_agent_step("ERR", "运行失败", str(exc))
        raise