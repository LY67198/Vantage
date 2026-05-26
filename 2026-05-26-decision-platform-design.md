# 企业智能决策中台 — 设计规格

## 概述

基于 LangGraph 多 Agent 协作的企业智能决策中台。用户用自然语言提问，系统调度 SQL Agent 查询数据、RAG Agent 检索文档，Report Agent 融合生成带来源引用的分析报告。

- **业务场景**：销售业绩分析（如 "Q2 华东区业绩为什么下滑？"）
- **Agent 框架**：LangGraph — Orchestrator + Send API 并行分发
- **LLM**：DeepSeek API（统一变量 `API_KEY`、`BASE_URL`、`MODEL`）
- **数据策略**：Phase 1 全 Mock，后续逐步替换为 Redis/SQL/真实 API
- **输出方式**：终端结构化输出（`log_agent_step`），后续迁移到 Streamlit/FastAPI

## 架构

```
                          START
                            │
                            ▼
                    ┌───────────────┐
                    │ Orchestrator   │
                    │ 解析用户问题     │
                    │ 拆解为子任务     │
                    └───────┬───────┘
                            │ Send API 并行分发
              ┌─────────────┼─────────────┐
              ▼             ▼
        ┌──────────┐ ┌──────────┐
        │ SQL Agent│ │RAG Agent │
        │ ReAct循环 │ │ ReAct循环 │
        │ Mock CRM  │ │ Mock文档  │
        └────┬─────┘ └────┬─────┘
             │            │
             └──────┬─────┘
                    ▼    (LangGraph join 语义：两路到齐才执行)
            ┌──────────────┐
            │ Report Agent  │
            │ 纯格式化,无工具  │
            │ 融合两路结果     │
            └──────┬───────┘
                   ▼
                  END
```

### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Orchestrator → Worker | Send API 全并行 | Phase 1 简单，扩展点已预留 |
| 并行范围 | 仅 SQL + RAG 并行 | Report 依赖两者输出，需串行等待 |
| Report 触发机制 | LangGraph join 语义（`sql→report` + `rag→report`） | 两路到齐自动执行 |
| SQL/RAG Agent | 内部 ReAct 循环 | 需要 tool calling（多轮查询） |
| Report Agent | 纯格式化节点，无工具 | 职责单一，一次 LLM 调用完成 |
| Report + Synthesizer | Phase 1 合并为一个节点 | 避免职责重叠，减少一次 LLM 调用 |
| State 合并 | `operator.add` reducer | 防止并行写入覆盖 |
| 路由扩展点 | Orchestrator 输出边 | 改两行变 `add_conditional_edges` |

## Agent 设计

### Orchestrator

```python
def orchestrator_node(state: AgentState) -> AgentState:
    # LLM 分析用户问题，识别需要哪些数据源
    response = llm.invoke(f"分析用户问题: {state['user_query']}...")
    log_agent_step("ORC", "🔍 分析完成", response.content)
    return {"messages": [response]}
```

- **职责**：解析用户自然语言问题，拆解子任务
- **工具**：无（纯 LLM 推理）
- **输出**：问题分析结果，存入 `messages`

### SQL Agent（ReAct 循环）

```
用户问题 → think（LLM 生成伪 SQL）→ act（执行 Mock 查询）→ think（判断结果是否足够）→ 输出结构化数据
```

- **工具**：`execute_query(sql: str)` — Mock 返回 CRM 销售数据
- **职责**：把自然语言转成查询逻辑 → 执行 → 返回数字 + 表格
- **输出**：
```python
{
    "region": "华东",
    "period": "2025-Q2",
    "revenue": 2340,         # 万元
    "yoy_change": -12.3,     # %
    "raw_rows": [...],       # 原始行数据
    "sql_executed": "SELECT ..."  # 调试用
}
```

### RAG Agent（ReAct 循环）

```
用户问题 → think（LLM 生成检索关键词）→ act（Mock 文档检索）→ think（判断是否需要更多文档）→ 输出相关片段
```

- **工具**：`search_docs(query: str, top_k: int)` — Mock 返回文档列表
- **职责**：从知识库检索相关复盘/策略文档
- **输出**：
```python
[{
    "title": "2025-Q2华东区销售复盘",
    "content": "...",
    "source": "内部复盘/2025-Q2-华东.docx",
    "score": 0.92
}, ...]
```

### Report Agent（纯格式化，无 ReAct）

```python
def report_node(state: AgentState) -> AgentState:
    # 前置检查：双路失败直接返回错误
    sql_ok = state["sql_result"] and "error" not in state["sql_result"][0]
    rag_ok = len(state["rag_result"]) > 0

    if not sql_ok and not rag_ok:
        return {"report": "⚠️ 数据服务暂时不可用，请稍后重试。"}

    prompt = f"""
    基于以下数据生成分析报告：
    SQL 结果: {state['sql_result']}
    RAG 结果: {state['rag_result']}
    格式要求: Markdown, 带数据表格, 带文档来源引用
    如有缺失数据，在报告中明确标注。
    """
    response = llm.invoke(prompt)
    log_agent_step("RPT", "✅ 报告生成", response.content, max_len=800)
    return {"report": response.content}
```

- **无工具，无 ReAct** — 一次 LLM 调用完成格式化 + 润色 + 完整性检查
- **前置检查**：SQL + RAG 双路同时失败时，直接返回错误提示，不生成误导性报告
- **输出**：带表格 + 来源引用的 Markdown 报告

## 状态设计

```python
import operator
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # 消息流（add_messages reducer 自动追加）
    messages: Annotated[list, add_messages]

    # 用户输入
    user_query: str

    # SQL Agent 输出 — operator.add 防止并行覆盖
    sql_result: Annotated[list, operator.add]
    # 每个元素: {"region": str, "period": str, "revenue": float,
    #            "yoy_change": float, "raw_rows": list, "sql_executed": str}

    # RAG Agent 输出 — operator.add 防止并行覆盖
    rag_result: Annotated[list, operator.add]
    # 每个元素: {"title": str, "content": str, "source": str, "score": float}

    # Report Agent 输出 — 单值，无竞争
    report: str
```

**关键约定：**
- 所有返回 dict 的 key 必须与 TypedDict 保持一致
- `messages` 使用 `add_messages` reducer，key 必须是 `messages`（不是 `message`）
- `sql_result` 和 `rag_result` 使用 `operator.add` reducer，Send API 并行写回时追加而非覆盖

## Mock 数据设计

```
decision-platform/
├── mock_data/
│   ├── __init__.py          # AVAILABLE_SCENARIOS = ["q2_east_china"]
│   ├── crm_sales.py         # SQL Agent Mock 数据源
│   └── knowledge_base.py    # RAG Agent Mock 数据源
```

### 数据格式

```python
# crm_sales.py
SCENARIOS = {
    "q2_east_china": {
        "region": "华东",
        "period": "2025-Q2",
        "revenue": 2340,
        "yoy_change": -12.3,
        "raw_rows": [
            {"city": "上海", "q2_2024": 1480, "q2_2025": 1280},
            {"city": "杭州", "q2_2024": 680, "q2_2025": 610},
            {"city": "南京", "q2_2024": 510, "q2_2025": 450},
        ],
    },
}
```

```python
# knowledge_base.py
SCENARIOS = {
    "q2_east_china": [
        {"title": "2025-Q2华东区销售复盘", "content": "...",
         "source": "内部复盘/2025-Q2-华东.docx", "score": 0.92},
        {"title": "华东市场策略调整建议", "content": "...",
         "source": "策略文档/华东-2025.md", "score": 0.85},
    ],
}
```

### 扩展方式

新场景 = 在两个 `SCENARIOS` 字典各加一个同名 key + 更新 `AVAILABLE_SCENARIOS`，零代码改动。

**约束：** 两个文件的 `SCENARIOS` key 必须同名。`main.py` 启动时 assert 校验，不一致直接报错。

## 终端输出设计

```python
# utils/logger.py
import time

COLORS = {
    "ORC": "\033[95m",  # 紫色 — Orchestrator
    "SQL": "\033[94m",  # 蓝色 — SQL Agent
    "RAG": "\033[92m",  # 绿色 — RAG Agent
    "RPT": "\033[93m",  # 黄色 — Report Agent
    "END": "\033[0m",   # 重置
}

def log_agent_step(agent: str, status: str, content: str, max_len: int = 500):
    """Phase 1 终端输出，Phase 2 直接复用为 SSE event"""
    color = COLORS.get(agent, "")
    timestamp = time.strftime("%H:%M:%S")
    print(f"\n{'─'*50}")
    print(f"{color}[{agent}] {timestamp} {status}\033[0m")
    print(f"{content[:max_len]}{'...' if len(content) > max_len else ''}")
```

**运行时效果：**
```
──────────────────────────────────────────────────
[ORC] 14:23:00 🔍 分析用户问题
识别到需要: SQL查询(销售数据) + 文档检索(历史策略)
──────────────────────────────────────────────────
[SQL] 14:23:01 ⚡ 执行查询
SELECT region, revenue, yoy_change FROM ...
──────────────────────────────────────────────────
[RAG] 14:23:01 📚 检索文档
找到 3 份相关文档 (score > 0.7)
──────────────────────────────────────────────────
[SQL] 14:23:02 ✅ 查询完成
华东区 Q2 营收 2340万, 同比 -12.3%
──────────────────────────────────────────────────
[RAG] 14:23:03 ✅ 检索完成
Q2华东复盘 / 华东策略建议 / 竞品动态分析
──────────────────────────────────────────────────
[RPT] 14:23:04 📝 生成报告
## 华东区 Q2 业绩分析...
```

## 错误处理

| 场景 | 处理策略 |
|------|----------|
| Orchestrator LLM 调用失败 | `RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0)` |
| SQL Agent LLM 调用失败 | `RetryPolicy(max_attempts=3)` |
| RAG Agent LLM 调用失败 | `RetryPolicy(max_attempts=3)` |
| SQL Mock 查询异常 | 返回 `{"error": str}`，Report 标注 "数据暂不可用" |
| RAG 检索无结果 | 返回 `[]`，Report 标注 "未找到相关文档" |
| SQL + RAG 双路同时失败 | Report 前置检查，直接返回 `⚠️ 数据服务暂时不可用，请稍后重试。` |
| Report Agent LLM 调用失败 | `RetryPolicy` 重试 1 次 → 降级为模板拼接 |
| SCENARIOS key 不匹配 | `main.py` 启动 assert，不一致直接退出 |

### RetryPolicy 配置

```python
from langgraph.types import RetryPolicy

retry = RetryPolicy(
    max_attempts=3,
    initial_interval=0.5,
    backoff_factor=2.0
)
# 应用于: orchestrator, sql_agent, rag_agent, report_agent
```

### Report Agent 降级模板

```python
# report_agent.py
FALLBACK_TEMPLATE = """
## 分析报告（降级模式）

### 数据摘要
{sql_summary}

### 相关文档
{rag_summary}

> ⚠️ 报告生成服务暂时异常，以上为原始数据直接呈现。
"""

def _fallback_report(sql_result, rag_result) -> str:
    sql_summary = str(sql_result) if sql_result else "暂无数据"
    rag_summary = "\n".join(
        f"- {doc['title']}" for doc in rag_result
    ) if rag_result else "暂无文档"
    return FALLBACK_TEMPLATE.format(
        sql_summary=sql_summary,
        rag_summary=rag_summary
    )
```

## 目录结构

```
decision-platform/
├── mock_data/
│   ├── __init__.py          # AVAILABLE_SCENARIOS = ["q2_east_china"]
│   ├── crm_sales.py         # SQL Agent Mock 数据源
│   └── knowledge_base.py    # RAG Agent Mock 数据源
├── graph/
│   ├── __init__.py
│   ├── state.py             # AgentState TypedDict
│   ├── orchestrator.py      # Orchestrator 节点 — LLM 问题解析
│   ├── sql_agent.py         # SQL Agent — ReAct 循环 + execute_query 工具
│   ├── rag_agent.py         # RAG Agent — ReAct 循环 + search_docs 工具
│   ├── report_agent.py      # Report Agent — 纯格式化, 无工具
│   └── builder.py           # 构建整张 Graph
├── tools/
│   ├── __init__.py
│   ├── sql_tools.py         # execute_query (Mock)
│   └── rag_tools.py         # search_docs (Mock)
├── utils/
│   ├── __init__.py
│   └── logger.py            # log_agent_step — 结构化终端输出
├── main.py                  # 入口：加载场景 → 构建 Graph → 运行
├── pyproject.toml
└── .env                     # API_KEY, BASE_URL, MODEL
```

## 演进路线

```
Phase 1（当前）        Phase 2（+Redis）       Phase 3（+SQL）         Phase 4（+部署）
───────────────       ─────────────────       ────────────────       ────────────────
Mock 数据              Redis 缓存              真实 DB 连接            Docker 容器化
全并行                 会话管理                 PostgreSQL/MySQL       FastAPI + 前端
终端输出              API 响应缓存             Text-to-SQL 工具       权限系统
                      速率限制                 Schema 管理            可观测性
```

**Phase 1 → Phase 2 衔接点：**
- `tools/sql_tools.py`：`execute_query` 内部查 Mock → 改为查 Redis 缓存 → 最终查真实 DB，接口不变
- `tools/rag_tools.py`：`search_docs` 内部查 Mock → 改为向量检索（Redis 存 embedding），接口不变
- `utils/logger.py`：`log_agent_step` → 改一行 print 变 yield SSE event，函数签名不变

**路由扩展点（从全并行到智能路由）：**
```python
# Phase 1 — graph/builder.py
graph.add_edge("orchestrator", "sql_agent")
graph.add_edge("orchestrator", "rag_agent")

# Phase 2 — 只改这里
def route(state):
    needs = state.get("required_agents", ["sql", "rag"])
    sends = []
    if "sql" in needs:
        sends.append(Send("sql_agent", state))
    if "rag" in needs:
        sends.append(Send("rag_agent", state))
    return sends
workflow.add_conditional_edges("orchestrator", route)
```

## LangGraph 知识点覆盖

| 知识点 | 落地位置 |
|--------|----------|
| StateGraph + TypedDict | `state.py` — AgentState |
| `bind_tools` | `sql_agent.py`, `rag_agent.py` — 各自绑定工具集 |
| ReAct 循环 | SQL Agent + RAG Agent 内部 `think → act → think` |
| Send API 并行分发 | `builder.py` — Orchestrator → [SQL, RAG] |
| 条件路由（预留） | `builder.py` — 替换全并行边为 `add_conditional_edges` |
| RetryPolicy | `orchestrator.py`, `sql_agent.py`, `rag_agent.py`, `report_agent.py` |
| Middleware | `utils/logger.py` 或独立 `middleware.py` — Token 日志 |
| 层级 Supervisor（预留） | Phase 2 — Orchestrator 上层加 Master 编排 |

## 依赖

```
langgraph >= 1.2
langchain >= 1.3
langchain-openai >= 1.2  (DeepSeek 兼容 OpenAI 协议)
python-dotenv
```

## 约束

- DeepSeek 配置通过 `API_KEY`、`BASE_URL`、`MODEL` 环境变量
- Phase 1 全 Mock 数据，不依赖外部 API
- 新增场景只需在 `mock_data/` 加数据文件，不改图代码
- 所有 `graph/` 返回 dict 的 key 必须与 AgentState TypedDict 严格一致
- `messages` key 是 `messages`（复数），配合 `add_messages` reducer
