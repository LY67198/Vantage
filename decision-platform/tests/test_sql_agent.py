"""sql_agent_node 单元测试 — 覆盖 ReAct 循环各分支。"""
from unittest.mock import MagicMock, patch
import pytest

from graph.state import AgentState
from graph.sql_agent import sql_agent_node, MAX_ITERATIONS


# ── helpers ──────────────────────────────────────────────────────────

def _make_mock_ai_message(tool_calls=None, content="推理中..."):
    """构造模拟 AIMessage。tool_calls 用 dict 格式（langchain-core 1.4 实测为 dict）。"""
    msg = MagicMock()
    msg.tool_calls = tool_calls or []
    msg.content = content
    return msg


def _mock_tool_call(name="execute_query", args=None, tc_id="call_001"):
    return {"name": name, "args": args or {"sql": "SELECT * FROM sales"}, "id": tc_id}


def _base_state(user_query="Q2 华东业绩怎么样？"):
    return {
        "messages": [],
        "user_query": user_query,
        "sql_result": [],
        "rag_result": [],
        "report": "",
    }


# ── 1. 首轮成功查询 ──────────────────────────────────────────────────

def test_successful_query_first_attempt():
    """首轮 LLM 返回 tool_call → execute_query 返回有效数据 → 直接返回。"""
    mock_result = {"region": "华东", "period": "2025-Q2", "revenue": 2340, "yoy_change": -12.3}

    with patch("graph.sql_agent.get_llm") as mock_get_llm, \
         patch("graph.sql_agent.execute_query") as mock_tool:

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        # 模拟 LLM 返回带有 tool_call 的 AIMessage
        mock_llm.invoke.return_value = _make_mock_ai_message(
            tool_calls=[_mock_tool_call(args={"sql": "SELECT ..."})]
        )
        mock_get_llm.return_value = mock_llm

        mock_tool.invoke.return_value = mock_result

        state = _base_state()
        result = sql_agent_node(state)

    assert "sql_result" in result
    assert len(result["sql_result"]) == 1
    assert result["sql_result"][0]["region"] == "华东"
    assert result["sql_result"][0]["revenue"] == 2340
    assert "messages" in result


# ── 2. LLM 未生成工具调用 ─────────────────────────────────────────────

def test_no_tool_calls_returns_error():
    """首轮 LLM 返回空 tool_calls → 返回 error 字典。"""
    with patch("graph.sql_agent.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = _make_mock_ai_message(
            tool_calls=[], content="我无法理解这个问题"
        )
        mock_get_llm.return_value = mock_llm

        state = _base_state()
        result = sql_agent_node(state)

    assert "sql_result" in result
    assert "error" in result["sql_result"][0]
    assert "messages" in result


# ── 3. 首轮查询返回 error，第二轮成功 ─────────────────────────────────

def test_retry_after_query_error():
    """首轮 execute_query 返回 error → Agent 再试 → 第二轮成功。"""
    error_result = {"error": "查询失败"}
    success_result = {"region": "华东", "period": "2025-Q2", "revenue": 2340}

    with patch("graph.sql_agent.get_llm") as mock_get_llm, \
         patch("graph.sql_agent.execute_query") as mock_tool:

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        # 两轮都返回 tool_call
        mock_llm.invoke.return_value = _make_mock_ai_message(
            tool_calls=[_mock_tool_call()]
        )
        mock_get_llm.return_value = mock_llm

        # 第一次返回 error，第二次返回成功
        mock_tool.invoke.side_effect = [error_result, success_result]

        state = _base_state()
        result = sql_agent_node(state)

    assert result["sql_result"][0]["region"] == "华东"
    assert mock_tool.invoke.call_count == 2


# ── 4. 达到最大迭代次数 ───────────────────────────────────────────────

def test_max_iterations_exhausted():
    """每轮 execute_query 都返回 error → 达 MAX_ITERATIONS 后退出。"""
    error_result = {"error": "查询失败"}

    with patch("graph.sql_agent.get_llm") as mock_get_llm, \
         patch("graph.sql_agent.execute_query") as mock_tool:

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = _make_mock_ai_message(
            tool_calls=[_mock_tool_call()]
        )
        mock_get_llm.return_value = mock_llm

        mock_tool.invoke.return_value = error_result

        state = _base_state()
        result = sql_agent_node(state)

    assert "error" in result["sql_result"][0]
    assert mock_tool.invoke.call_count == MAX_ITERATIONS


# ── 5. 非 execute_query 工具调用被跳过 ────────────────────────────────

def test_skips_other_tools():
    """LLM 调用了其他 tool → 跳过，本轮空转后下一轮可能成功。"""
    success_result = {"region": "华东", "period": "2025-Q2", "revenue": 2340}

    with patch("graph.sql_agent.get_llm") as mock_get_llm, \
         patch("graph.sql_agent.execute_query") as mock_tool:

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        # 第一轮调用错误的 tool，第二轮才是 execute_query
        mock_llm.invoke.side_effect = [
            _make_mock_ai_message(
                tool_calls=[_mock_tool_call(name="unknown_tool")]
            ),
            _make_mock_ai_message(
                tool_calls=[_mock_tool_call(name="execute_query")]
            ),
        ]
        mock_get_llm.return_value = mock_llm

        mock_tool.invoke.return_value = success_result

        state = _base_state()
        result = sql_agent_node(state)

    assert result["sql_result"][0]["region"] == "华东"
    # execute_query.invoke 只在第二轮被调用一次
    assert mock_tool.invoke.call_count == 1


# ── 6. 返回值 key 与 AgentState 兼容 ──────────────────────────────────

def test_return_keys_match_agent_state():
    """返回值 key 必须与 AgentState TypedDict 一致。"""
    valid_keys = {"messages", "user_query", "sql_result", "rag_result", "report"}

    success_result = {"region": "华东", "revenue": 2340}

    with patch("graph.sql_agent.get_llm") as mock_get_llm, \
         patch("graph.sql_agent.execute_query") as mock_tool:

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = _make_mock_ai_message(
            tool_calls=[_mock_tool_call()]
        )
        mock_get_llm.return_value = mock_llm
        mock_tool.invoke.return_value = success_result

        result = sql_agent_node(_base_state())

    # 返回的所有 key 必须是 AgentState 中存在的 key
    for key in result:
        assert key in valid_keys, f"返回了非法 key: {key}"


# ── 7. sql_result 使用 operator.add 语义 ──────────────────────────────

def test_sql_result_is_list():
    """sql_result 必须是 list — operator.add reducer 依赖 list 语义。"""
    with patch("graph.sql_agent.get_llm") as mock_get_llm, \
         patch("graph.sql_agent.execute_query") as mock_tool:

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = _make_mock_ai_message(
            tool_calls=[_mock_tool_call()]
        )
        mock_get_llm.return_value = mock_llm
        mock_tool.invoke.return_value = {"region": "华东"}

        result = sql_agent_node(_base_state())

    assert isinstance(result["sql_result"], list), \
        f"sql_result 必须是 list，实际是 {type(result['sql_result'])}"
