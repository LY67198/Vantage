# CLAUDE.md — Vantage 项目上下文

## 项目概述

Vantage（企业智能决策中台），基于 LangGraph 多 Agent 协作。用户自然语言提问 → SQL Agent 查数据 + RAG Agent 检索文档 → Report Agent 融合生成 Markdown 分析报告。

| 项目 | 内容 |
|------|------|
| 业务场景 | 销售业绩分析（如「Q2 华东区业绩为什么下滑？」） |
| Agent 框架 | LangGraph — Orchestrator + Send API 并行分发 |
| LLM | DeepSeek API（兼容 OpenAI 协议，ChatOpenAI 调用） |
| 数据策略 | Phase 1 Mock → Phase 2 真实 DB → Phase 3 向量库 + 缓存 |
| 开发周期 | 8 周 / 40 天 |

## 当前阶段

**Phase 2**（Week 3–4）：PostgreSQL + ChromaDB 真实数据接入。Phase 1 已完成。

### Phase 1（已完成 ✅）

| 模块 | 文件 | 状态 |
|------|------|------|
| AgentState | `graph/state.py` | ✅ |
| LLM 配置 | `graph/llm.py` | ✅ 懒加载单例，`get_llm()` 首次调用时创建，import 不依赖 .env |
| Mock 数据层 | `mock_data/` | ✅ CRM + 知识库 + 场景注册 + 校验 |
| 工具层 | `tools/sql_tools.py` `tools/rag_tools.py` | ✅ `@tool` 装饰，Phase 演进接口不变 |
| 日志 | `utils/logger.py` | ✅ 终端彩色日志，预留 SSE 复用 |
| Orchestrator | `graph/orchestrator.py` | ✅ LLM 分析问题、识别实体、拆解子任务 |
| SQL Agent | `graph/sql_agent.py` | ✅ 手写 ReAct 循环，7 个单元测试通过 |
| RAG Agent | `graph/rag_agent.py` | ✅ 手写 ReAct 循环，8 个单元测试通过 |
| Report Agent | `graph/report_agent.py` | ✅ 融合 + 降级模板 |
| Graph 构建 | `graph/builder.py` | ✅ StateGraph + Send API 并行 + RetryPolicy + join |
| 入口联调 | `main.py` | ✅ 全链路跑通（Orchestrator → SQL/RAG 并行 → Report） |

### Phase 2 进度（Week 3：PostgreSQL 接入）

| 任务 | 状态 | 说明 |
|------|------|------|
| PostgreSQL 环境搭建 | ✅ | Windows 本地 PostgreSQL 16，`vantage` 数据库，`sales_records` 表 |
| 测试数据导入 | ✅ | `scripts/seed_data.py`，华东/华南/华北/华中 2024-2025 数据 |
| `psycopg2-binary` 依赖 | ✅ | 已加入 `pyproject.toml`，连接通道打通 |
| `execute_query` 工具升级 | ✅ | Mock → 真实 DB 查询 |
| Schema 管理 | ✅ | 自动注入表结构到 LLM prompt |
| SQL Agent 联调 | ✅ | 验证复杂查询正确率 |
| ChromaDB 环境搭建 | ✅ | Week 4 — PersistentClient + DashScopeEmbeddings，余弦距离 |
| `search_docs` 工具升级 | ✅ | Mock → ChromaDB 向量检索，score = 1 - cosine_distance |
| RAG Agent 联调 | ✅ | Week 4 — LLM 生成检索词，命中结果 0.838 相似度 |
| 端到端联调 | ✅ | Week 4 — tests/test_e2e.py，三 Agent 协同通过 |

### PostgreSQL 环境备忘

```
服务名: postgresql-16
数据目录: C:\Program Files\PostgreSQL\16\data\
认证方式: pg_hba.conf 中 127.0.0.1/32 和 ::1/128 改为 trust（本地免密码）
连接参数: host=localhost port=5432 dbname=vantage user=postgres

# 手动启动服务（管理员终端）
net start postgresql-16

# 初始化数据目录（仅在安装后首次需要）
pg_ctl init -D "C:\Program Files\PostgreSQL\16\data"

# 重新加载配置（修改 pg_hba.conf 后）
pg_ctl reload -D "C:\Program Files\PostgreSQL\16\data"

# 验证连接
psql -U postgres -d vantage
```

> **注意：** `services.msc` 中将 PostgreSQL 启动类型改为「自动」，否则每次重启需手动启动。

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Orchestrator → Worker | Send API 全并行 | Phase 1 简单，扩展点已预留 |
| SQL/RAG Agent | 内部 ReAct 循环 | 需要 tool calling 支持多轮推理 |
| Report Agent | 纯格式化，无工具 | 职责单一，一次 LLM 调用完成 |
| Report + Synthesizer | 合并为一个节点 | 避免职责重叠，减少一次 LLM 调用 |
| Report 触发 | LangGraph join 语义 | 两路到齐自动执行，零额外代码 |
| State 合并 | `operator.add` reducer | 防止并行写入时字段覆盖 |
| 路由扩展 | Orchestrator 输出边预留 | Phase 2 两行代码升级智能路由 |

## Agent 实现方式

**Agent 内部逻辑全部手写，不使用 `create_react_agent`。** LangGraph 负责编排层（State、边、Send API、join、RetryPolicy），Agent 内部 ReAct 循环自己写。

```python
# 手写 ReAct 模板
llm_with_tools = llm.bind_tools([tool])
messages = [HumanMessage(content=system_prompt + user_query)]

for i in range(MAX_ITERATIONS):
    response = llm_with_tools.invoke(messages)
    messages.append(response)

    if not response.tool_calls:
        # 无工具调用 → 推理完成或失败
        break

    for tool_call in response.tool_calls:
        result = tool.invoke(tool_call["args"])
        messages.append(ToolMessage(content=str(result), ...))

        if success_condition(result):
            return result  # 拿到有效数据，提前退出
```

对比 `create_react_agent`：

| | `create_react_agent` | 手写 ReAct |
|---|---|---|
| 日志 | 黑盒，插不进去 | 每一步打彩色日志 + 时间戳 |
| 输出格式 | LLM 自由文本 | 结构化 dict/list，精确控制字段 |
| 错误处理 | 异常直接抛出 | 返回 `{"error": str}`，下游可识别 |
| Phase 2 SSE | 无法控制事件粒度 | 每个 act 节点可发 SSE event |

### SDK 选型

**底层用 `langchain-openai`（ChatOpenAI），不用 DeepSeek 官方 SDK。**

```
手写 ReAct 循环（你的代码）
  → llm.bind_tools([tool])       ← langchain-core
  → ChatOpenAI.invoke(messages)  ← langchain-openai
  → DeepSeek API（OpenAI 兼容协议）
```

理由：`bind_tools` + `HumanMessage`/`AIMessage`/`ToolMessage` 三层是 LangChain 最稳定的 API，依赖极薄，不构成绑定风险。换成 DeepSeek SDK 反而要自己拼 tool schema、处理消息格式，多出大量无聊代码。

### 已验证的 API 行为（langchain-core 1.4.0 / langgraph 1.x）

| 检查点 | 结论 |
|--------|------|
| `AIMessage.tool_calls` 元素类型 | **`dict`** — 用 `tc["name"]` / `tc["args"]` / `tc["id"]` 访问。升级 langchain-core 版本前需验证，后续版本可能改为 `ToolCall` 对象 |
| `add_edge(["A", "B"], "C")` list 语法 | **支持** — `StateGraph.add_edge(start_key: str \| list[str], end_key: str)`，多节点 join 写法有效 |
| `Send` + `operator.add` 并行安全 | **安全** — Send API 为每个分支拷贝 state，各自写不同 key 不会冲突 |
| `RetryPolicy` + 节点内部 try/except | **RetryPolicy 不生效** — 节点自行 catch 异常后不往外抛，graph 层收不到错误，不会触发重试。Report Agent 有意如此（降级 > 重试） |

### Orchestrator（无工具，纯 LLM 推理）
- 解析用户自然语言问题，识别所需数据源，拆解子任务
- 输出存入 `messages`，格式：`{"messages": [response]}`

### SQL Agent（ReAct 循环 + execute_query 工具）
- 自然语言 → 生成 SQL → 执行查询 → 判断结果是否足够
- 输出格式：`{"region": "华东", "period": "2025-Q2", "revenue": 2340, "yoy_change": -12.3, "raw_rows": [...], "sql_executed": "SELECT ..."}`

### RAG Agent（ReAct 循环 + search_docs 工具）
- 生成检索关键词 → 检索文档 → 判断是否需要更多
- 输出格式：`[{"title": "...", "content": "...", "source": "...", "score": 0.92}]`
- score < 0.7 自动过滤，`search_docs` 默认 top_k=3
- 用 `collected_docs.extend(docs)` 累积多轮结果，`return` 时用 `collected_docs` 而非 `docs`（当前批次），保持累积语义一致

### Report Agent（无工具，纯格式化 + 降级模板）
- 融合 SQL + RAG 两路结果，一次 LLM 调用生成 Markdown 报告
- 前置检查：`sql_ok = bool(sql_result) and isinstance(sql_result[0], dict) and "error" not in sql_result[0]`
- 双路同时失败直接返回 `⚠️ 数据服务暂时不可用，请稍后重试。`
- LLM 调用内部重试 2 次 → 失败降级为 `FALLBACK_TEMPLATE`（注意：不用 RetryPolicy，见上方 API 行为表）

## State 设计

```python
class AgentState(TypedDict):
    messages:   Annotated[list, add_messages]   # 消息流，自动追加
    user_query: str                             # 用户输入
    sql_result: Annotated[list, operator.add]   # SQL 输出，防并行覆盖
    rag_result: Annotated[list, operator.add]   # RAG 输出，防并行覆盖
    report:     str                             # Report 输出，单值无竞争
```

**关键约定：** 所有节点返回 dict 的 key 必须与 TypedDict 严格一致。`messages` 必须是复数。`sql_result` / `rag_result` 用 `operator.add` 追加而非覆盖。

## 日志设计

```python
# utils/logger.py
COLORS = {"ORC": "\033[95m", "SQL": "\033[94m", "RAG": "\033[92m", "RPT": "\033[93m"}

def log_agent_step(agent: str, status: str, content: str, max_len: int = 500):
    """Phase 1 终端输出 → Phase 2 直接复用为 SSE event，函数签名不变"""
    # 输出格式: [AGENT] HH:MM:SS emoji status
    #           content (截断 max_len)
```

## 错误处理

| 场景 | 策略 |
|------|------|
| 任意节点 LLM 调用失败 | RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0) — orchestrator/sql/rag 三个节点绑定 |
| SQL 查询异常 | 返回 `{"error": str}`，Report 标注「数据暂不可用」 |
| RAG 检索无结果 | 返回 `[]`，Report 标注「未找到相关文档」 |
| SQL + RAG 双路同时失败 | Report 前置检查，直接返回错误提示，不生成误导性报告 |
| Report LLM 调用失败 | **Report 节点内部 try/except 吃掉异常 → RetryPolicy 不会触发。**改为内部 2 次尝试后降级 `FALLBACK_TEMPLATE` |
| SCENARIOS key 不匹配 | `main.py` 启动 assert 校验，不一致直接退出 |

## Mock 数据格式

```python
# mock_data/__init__.py
AVAILABLE_SCENARIOS = ["q2_east_china"]

# mock_data/crm_sales.py — SCENARIOS["q2_east_china"] = {
#     "region": "华东", "period": "2025-Q2", "revenue": 2340, "yoy_change": -12.3,
#     "raw_rows": [{"city": "上海", "q2_2024": 1480, "q2_2025": 1280}, ...]
# }

# mock_data/knowledge_base.py — SCENARIOS["q2_east_china"] = [
#     {"title": "...", "content": "...", "source": "...", "score": 0.92}, ...
# ]
```

**新增场景：** 两个文件各加同名 key + 更新 `AVAILABLE_SCENARIOS`，Agent 代码零改动。

## 工具接口演进（"先 Mock 后替换"）

每 Phase 学一个新技能 → 工具**内部实现**替换，**外部接口不变**，Agent/Graph 代码零改动：

```
Phase 1: execute_query → Mock 数据（已完成）
Phase 2: execute_query → 真实 PostgreSQL 查询（进行中）
Phase 3: execute_query → 先查 Redis 缓存 → 未命中查 PostgreSQL → 写缓存
```

```
Phase 1: search_docs → Mock 数据（已完成）
Phase 2: search_docs → ChromaDB 向量检索
Phase 3: search_docs → 先查 Redis 缓存 → 未命中查 ChromaDB → 写缓存
```

**核心原则：** 学什么补什么，接口不动。每次只改 `tools/` 内部，不改 `graph/`、不改 `main.py`。

> **Phase 2/3 调整说明：** 原计划 Phase 2 先做 Redis 缓存再查 Mock，实际调整为先接真实 DB 和 ChromaDB，让数据层先扎实，再往上加缓存——缓存效果可观测（Mock 0ms vs 真实 DB 3~5s）。

## Phase 2 路由扩展点

```python
# Phase 1-2（当前：全并行）
graph.add_edge("orchestrator", "sql_agent")
graph.add_edge("orchestrator", "rag_agent")

# Phase 3（替换为条件路由）
def route(state):
    needs = state.get("required_agents", ["sql", "rag"])
    sends = []
    if "sql" in needs: sends.append(Send("sql_agent", state))
    if "rag" in needs: sends.append(Send("rag_agent", state))
    return sends
workflow.add_conditional_edges("orchestrator", route)
```

## 技术栈演进

| 层级 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|
| 数据库 | Mock | PostgreSQL (4表) | PostgreSQL | PostgreSQL |
| 向量检索 | Mock | ChromaDB | ChromaDB | ChromaDB |
| 缓存 | — | — | Redis (会话+响应缓存+速率限制) | Redis |
| API | — | — | — | FastAPI + SSE 流式 |
| 前端 | 终端日志 | 终端日志 | 终端日志 | Streamlit |
| 部署 | 本地 | 本地 | 本地 | Docker Compose + 云服务器 |

## 依赖（UV 管理）

本项目使用 [UV](https://docs.astral.sh/uv/) 作为包管理器和虚拟环境工具。

**常用命令：**

| 命令 | 用途 |
|------|------|
| `uv sync` | 同步依赖到 `.venv`，自动创建 lock 文件 |
| `uv run python main.py` | 在虚拟环境中运行脚本 |
| `uv run pytest` | 在虚拟环境中运行测试 |
| `uv add <package>` | 添加新依赖 |
| `uv lock --upgrade` | 升级全部依赖到最新兼容版本 |
| `uv run python -c "..."` | 执行一行 Python 代码 |
| `uv pip list` | 查看已安装的包 |

**关键约定：**
- 执行目录：所有 `uv run` 命令在 `decision-platform/` 目录下执行
- 测试命令：`cd decision-platform && uv run pytest`
- 运行入口：`cd decision-platform && uv run python main.py`
- 添加依赖：`cd decision-platform && uv add <package>`

```toml
# Phase 1-2（当前）
dependencies = [
    "langgraph>=1.2",
    "langchain>=1.3",
    "langchain-openai>=1.2",
    "python-dotenv>=1.0",
    "psycopg2-binary>=2.9.12",
]

# Phase 3-4（后续添加）
# "redis", "chromadb", "sentence-transformers", "fastapi", "uvicorn", "streamlit"
```

## 代码约定

- 目录结构顶层是 `decision-platform/`，`main.py` 和 `graph/`、`tools/` 平级
- 所有 `graph/` 节点函数返回 dict，key 必须与 AgentState TypedDict 严格一致
- `messages` key 是复数 `messages`，配合 `add_messages` reducer
- 工具接口 `execute_query` / `search_docs` 跨 Phase 保持不变，内部实现替换（Mock → Redis → 真实 DB）
- LLM 配置统一从 `graph/llm.py` 导入：`from graph.llm import get_llm`，函数内 `llm = get_llm()` 懒加载。不要模块级 `from graph.llm import llm`（旧模式，import 即 crash）

## 踩过的坑

### 1. `tool_call["args"]` 是 dict，不要用 `()` 调用

```python
# ❌ TypeError: 'dict' object is not callable
tool_args = tool_call.get("args", {})
sql = tool_args("sql", "")

# ✅ 正确
sql = tool_args.get("sql", "")
```

**原因：** `AIMessage.tool_calls` 元素是 dict，`tc["args"]` 返回 dict，不是函数。

### 2. `{"字符串"}` 在 Python 中是 set literal，不是 dict

```python
# ❌ 创建了 set，LangGraph 拿到 set 不可预期
return {"查询失败"}

# ✅ 正确 — 返回 dict，key 必须匹配 AgentState
return {"sql_result": [{"error": "查询失败"}], "messages": messages}
```

**原因：** Python 语法 `{x}` 当 x 不是 `k: v` 对时解析为 set。写 `return {"sql_result": [...]}` 时别偷懒省 key。

### 3. 节点返回值 key 必须与 AgentState TypedDict 严格一致

LangGraph 用 TypedDict key 做 state update — 返回的 key 不在 TypedDict 中 → graph 编译不过或静默丢弃。每个 Agent 节点返回前自检：是否包含 `messages` / `sql_result` / `rag_result` / `report` 中的必要项。

### 4. 跨 Agent 复制代码时遗漏修改 state key

```python
# ❌ RAG Agent 照抄 SQL Agent，返回了 sql_result
return {"sql_result": [{"error": "LLM 未生成工具调用", "raw_output": content}]}

# ✅ 正确 — RAG Agent 应返回 rag_result，且必须带上 messages
return {"rag_result": [{"error": "LLM 未生成工具调用", "raw_output": content}], "messages": messages}
```

**原因：** 从 SQL Agent 复制 ReAct 模板代码时，批量替换遗漏了 `sql_result` → `rag_result`。跨 Agent 复制后必须逐行检查 state key。

### 5. `return` 写在 `for` 循环内部导致提前退出，只执行一轮

```python
# ❌ return 在 for i 循环体内 → 第一轮就跑路了
for i in range(MAX_ITERATIONS):
    ...
    for tool_call in response.tool_calls:
        ...
        if not docs:
            log_agent_step("RAG", "未命中", "...")
    # ↓ 这里 return 还在 for i 里面！
    return {"rag_result": collected_docs, "messages": messages}

# ✅ 正确 — return 放在 for 循环外面，跑完所有轮次再退出
for i in range(MAX_ITERATIONS):
    ...
    for tool_call in response.tool_calls:
        ...
# ↓ 缩进到 for 同级
return {"rag_result": collected_docs, "messages": messages}
```

**原因：** `log_agent_step` + `return` 对写，缩进判断失误。两个 Agent 节点末尾的兜底 return 必须与 `for i` 同级，而非在 `for` 内部。

### 6. `break` 跳出 for 循环后无 return → 函数隐式返回 None

```python
# ❌ break 后 for 循环外没有 return，函数返回 None
if not response.tool_calls:
    if i == 0:
        return {...}
    break  # ← 跳出循环，但循环外无 return

# ✅ 正确 — 循环外兜底 return
for i in range(MAX_ITERATIONS):
    ...
# 循环外兜底
return {"rag_result": collected_docs, "messages": messages}
```

**原因：** `break` 退出 for 循环后，LangGraph 收到 None 会导致不可预期的 state 合并行为。所有退出路径必须有显式 return dict。

### 7. `log_agent_step` 第一个参数大小写不一致导致颜色失效

```python
# ❌ 小写 "rag" — COLORS 字典没有这个 key，终端无颜色
log_agent_step("rag", "检索完成", ...)

# ✅ 大写 "RAG" — COLORS = {"RAG": "\033[92m", ...}，绿色输出
log_agent_step("RAG", "检索完成", ...)
```

**原因：** `COLORS` 字典 key 都是大写三字母（ORC/SQL/RAG/RPT），小写匹配不上，输出不带颜色。Agent 缩写统一大写。

### 8. Windows GBK 终端无法输出 emoji → UnicodeEncodeError

```python
# ❌ Windows 默认 GBK 编码，emoji 报错
# UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f50d'
log_agent_step("ORC", "🔍 分析完成", response.content)

# ✅ logger.py 顶部强制 UTF-8
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

**原因：** Windows 中文终端默认 GBK 编码，Python print 时 emoji（如 🔍⚡✅⚠️）超出 GBK 字符集。在 `utils/logger.py` 进口处 `reconfigure` 一次即可，所有后续 print 自动支持。

### 9. Report Agent — 前置条件逻辑与变量命名 bug

```python
# ❌ 两个 bug：
# 1. 条件写反：not sql_ok and rag_ok → "sql失败 + rag成功"时才报错，应该是 "双路同时失败"
# 2. 变量名 typo：repory → report

if not sql_ok and rag_ok:          # Bug 1: 应该是 not rag_ok
    repory = "数据库服务不可用..."   # Bug 2: repory → report
    return {"report": repory}

# ✅ 正确
if not sql_ok and not rag_ok:
    report = "数据服务暂时不可用，请稍后重试。"
    return {"report": report}
```

**原因：** 逻辑运算符失误 + 变量名拼写错误。双路不可用的场景 Phase 1 用 Mock 数据很难触发（两个数据源永远可用），但 Phase 3 接入真实 DB 后一定会触发。写完条件表达式后反向验证：如果 SQL 失败 + RAG 有数据，你期望走 return 还是继续？

### 10. Windows PostgreSQL 安装后 `initdb` 可能未自动执行

```bash
# 装完先验证能否连接
psql -U postgres
# 连不上 → 检查数据目录是否为空 → 手动 initdb
pg_ctl init -D "C:\Program Files\PostgreSQL\16\data"
# 再启动服务
net start postgresql-16
```

**原因：** Windows 安装包不一定自动执行 `initdb`，数据目录为空时 postmaster 无法启动。

### 11. 每次重启后 PostgreSQL 服务需要手动启动

```powershell
# 一劳永逸：services.msc → postgresql-16 → 启动类型改为「自动」
# 临时启动（管理员终端）：
net start postgresql-16
```

**原因：** 安装时默认启动类型是「手动」，Windows 开机不会自动拉起。

### 12. 本地开发用 `trust` 认证，`psycopg2` 连接不用传密码

```python
# pg_hba.conf 改完后：
# host    all    all    127.0.0.1/32    trust
# host    all    all    ::1/128         trust

# Python 连接无需 password 参数
conn = psycopg2.connect(host="localhost", port=5432, dbname="vantage", user="postgres")
```

**原因：** `scram-sha-256` 要求密码，本地开发用 `trust` 足够安全（仅本机可访问）。修改后 `pg_ctl reload` 让配置生效。生产环境必须切回密码认证。

### 13. 模块级别不要连数据库、读配置、调 LLM

```python
# ❌ 模块级代码 import 时立即执行 → DB 没启动时整个程序崩溃
# utils/schema.py
schema = get_schema()  # import 时就连数据库

# ✅ 改成函数内部调用
def get_schema():
    conn = psycopg2.connect(...)  # 调用时才连接
    ...
```

**原因：** Python `import` 时执行模块级代码。`psycopg2.connect()`、`open()`、`get_llm()` 等 I/O 操作如果放在模块级别，一旦资源不可用（DB 没启动、文件不存在、API key 未配置），整个程序连入口都进不去。规律：所有可能失败的外部依赖调用一律推迟到函数执行时，模块级只放无副作用的定义。

### 14. Text-to-SQL 必须告诉 LLM 枚举值和数据范围

```python
# ❌ LLM 不知道 region 的实际值，凭语言习惯猜 → WHERE region = '华东区' → 零结果
# ❌ LLM 不知道年份范围 → SELECT SUM(revenue) ... WHERE quarter = 'Q2' → 把 2024+2025 全加起来

# ✅ 在 system prompt 里注入 Schema + 枚举值
SCHEMA_INFO = """
CREATE TABLE sales_records (...);
-- region 枚举值: 华东, 华南, 华北, 华中
-- year 枚举值: 2024, 2025（默认使用 2025）
-- quarter 枚举值: Q1, Q2
"""
```

**原因：** LLM 不知道数据库里字段的实际取值，会基于语言习惯瞎猜（华东 → 华东区）。不告知年份范围时，生成的 SQL 很容易遗漏时间过滤条件。Schema 注入是 Text-to-SQL 的必选项，不是可选项。

### 15. Mock 换真实数据时，下游所有用到返回字段的地方都要检查

```python
# Mock 返回格式:
# {"region": "华东", "revenue": 2340, "yoy_change": -12.3, "raw_rows": [...]}

# 真实 DB 返回格式:
# {"columns": ["region", "quarter", "revenue", ...], "rows": [(...), (...)]}

# ❌ 日志代码还用 Mock 字段名取 → region=None, revenue=None
log_agent_step("SQL", "查询完成", f"region={result.get('region')}")

# ✅ 更新为适配新格式
log_agent_step("SQL", "查询完成", f"columns={result.get('columns')}, rows={len(result.get('rows', []))}")
```

**原因：** 走 Mock 时字段名是业务语义的（region/revenue/yoy_change），真实 DB 返回的是通用格式（columns/rows）。下游代码（日志、Agent 解析、Report 渲染）散布在多处，漏改一处就看到满屏 None。

### 16. PostgreSQL `NUMERIC` 类型 → Python `Decimal`，要手动转换

```python
# ❌ psycopg2 返回 Decimal 类型
# Decimal('1330') → str() 输出带包装 → json.dumps 报错 → 传给 LLM prompt 格式难看

# ✅ 在 execute_query 工具里统一转换
from decimal import Decimal
from datetime import date, datetime

def _serialize(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value

# rows = [(Decimal('1330'), date(2025, 4, 1)), ...]
# → rows = [(1330.0, '2025-04-01'), ...]
```

**原因：** PostgreSQL `NUMERIC` 在 Python 中映射为 `Decimal`（精确数值），`DATE` 映射为 `date`。这些类型 json 序列化不支持，`str()` 输出格式也不友好。在工具层统一做类型转换，Agent 永远拿到干净的 Python 原生类型（float/str/int）。

### 17. 下载 PostgreSQL 选 installer 不要选 binaries

```bash
# 官网有两个下载入口：
# - "Download the installer" → 安装向导 + 服务注册 + initdb 自动执行 ✅
# - "Download the binaries"  → 只给可执行文件，全部手动配置 ❌
```

**原因：** binaries 压缩包只含可执行文件，安装向导、服务注册、初始化脚本都没有。除非你有特殊需求（如定制安装路径、嵌入式部署），否则 installer 省心十倍。Phase 4 Docker 部署后这个问题自然消失。

### 18. `embed_documents()` 参数必须是 `List[str]`，传单个字符串会被逐字拆解

```python
# ❌ d["text"] 是字符串 "华东区 Q2 业绩下滑..." → Python 按字符迭代
#   相当于 embed_documents(["华", "东", "区", ...]) → 每个单字做 embedding，语义全毁
embeddings = [model.embed_documents(d["text"]) for d in docs]

# ✅ 方案 A：传 list，取第一个结果（推荐 — 用 document 编码模式）
texts = [d["text"] for d in docs]
embeddings = model.embed_documents(texts)

# ✅ 方案 B：单条文档用 embed_query（注意：query 编码模式，效果可能略差）
embedding = model.embed_query(d["text"])
```

**原因：** `embed_documents(texts: List[str])`，Python 中字符串是可迭代对象，`embed_documents("华东区")` 等价于 `embed_documents(["华", "东", "区"])`，对整个文档生成一个垃圾向量。同时 `embed_documents` 用 passage/document 编码模式，`embed_query` 用 query 编码模式，索引文档时应优先用 `embed_documents`。

### 19. ChromaDB 默认使用 L2 距离，`score = 1 - dist` 公式是余弦距离公式

```python
# ❌ 创建 collection 时未指定距离度量 → 默认 L2（欧氏距离平方）
#    score = 1 - dist 公式对 L2 无效 → 分数全是负数或很低
collection = client.get_or_create_collection(name="vantage_docs")

# ✅ 显式指定余弦距离，使 score = 1 - dist ∈ [-1, 1]
collection = client.get_or_create_collection(
    name="vantage_docs",
    metadata={"hnsw:space": "cosine"}
)
```

**原因：** ChromaDB 默认 `hnsw:space` 为 `"l2"`（平方 L2），而你的 filtering 逻辑 `score = round(1 - dist, 4)` 和 `score >= 0.7` 是按余弦距离设计的。两个度量不匹配会导致语义相似的文档也被过滤掉。创建 collection 时把度量设为 `"cosine"`，余弦距离 ∈ [0, 2]，`1 - dist` 恰好是余弦相似度 ∈ [-1, 1]。

### 20. 修改 `hnsw:space` 后必须删除旧 collection 重建

```bash
# 改完代码后 chroma_data 目录还在 → 旧 collection 仍是 L2 度量
rm -rf chroma_data
python scripts/init_chroma.py  # 重建为 cosine 度量
```

**原因：** `get_or_create_collection` 在 collection 已存在时直接返回，不会修改已有 collection 的 `hnsw:space`。必须删掉 persistent 数据目录重建。

### 21. ChromaDB 客户端不要用相对路径 `./chroma_data`

```python
# ❌ 相对路径依赖 CWD → 从不同目录跑脚本指向不同的 chroma_data
_client = chromadb.PersistentClient(path="./chroma_data")

# ✅ 以 chroma_client.py 所在文件位置为锚，推导项目根目录
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent  # utils/ → 项目根
_client = chromadb.PersistentClient(path=str(_project_root / "chroma_data"))
```

**原因：** Python 中相对路径基于当前工作目录（CWD），不基于源文件位置。从不同目录执行脚本时会找到不同的（或空的）chroma_data，导致「有数据但查不到」或「数据写到了意想不到的位置」。

### 22. LangChain 管模型，chromadb 管存储，不要用 LangChain Chroma 封装

```python
# ✅ 当前架构：原生 chromadb + LangChain 只管 embedding
from langchain_community.embeddings import DashScopeEmbeddings  # embedding
import chromadb                                                  # 存储/检索

# ❌ 不建议：多一层 langchain-chroma 封装，黑盒看不到 distances
from langchain_chroma import Chroma
```

**原因：** 原生 `chromadb` 让你直接拿到 `query()` 返回的 `distances`、`metadatas`，debug 时 `print` 一目了然。LangChain 封装隐藏了这些细节，出问题只能猜。跟选 `psycopg2` 不选 ORM 同理：底层库给控制力，封装层只用于你需要的部分（embedding），不用于全部。

### 23. 跨 Agent 复制 ReAct 代码时，tool 参数名也要检查

```python
# SQL Agent: execute_query 的参数是 sql
tool_args.get("sql", "")  # ✅ 正确

# ❌ RAG Agent: 照抄 SQL Agent，把参数名改成了 "RAG"
#    但 search_docs 的参数是 query，LLM 生成的 tool_call 也是 query
tool_args.get("RAG", "")  # → 永远取到默认值 ""，search_docs 收到空查询

# ✅ 正确 — 与工具函数签名一致
tool_args.get("query", "")
```

**原因：** 跨 Agent 复制 ReAct 模板不止要改 state key（`sql_result` → `rag_result`），还要改 tool 参数名。LLM 生成 tool_call 时参数名与 `@tool` 函数签名一致（`search_docs(query: str, ...)` → `{"query": "..."}`），你读的时候必须用同一个名字。

### 24. PostgreSQL binaries 版本没有 Windows 服务，用 `pg_ctl` 启动

```bash
# ❌ binaries 版本没有注册 Windows 服务，net start 找不到
net start postgresql-16  # → 服务名无效

# ✅ 直接用 pg_ctl 启动
"D:/P_SQL/.../pgsql/bin/pg_ctl" start -D "D:/P_SQL/.../pgsql/data"
```

**原因：** 官网下载的 binaries 压缩包只含可执行文件，不会注册 Windows 系统服务。每次重启电脑后需要手动 `pg_ctl start`。installer 版本会自动注册服务（`net start postgresql-16` 可用）。Phase 4 Docker 部署后不再需要手动管理。

### 25. `print` 是最有效的向量检索 debug 工具

```python
# 在 search_docs 里加这行，排查效率提升 10 倍
print("原始distances：", results["distances"])
# → [[]]         → collection 为空或 embedding 全毁
# → [0.64, 1.35] → 有结果但距离 > 1 说明度量不匹配（L2 vs cosine）
# → [0.16, 0.68] → 余弦距离正常，score = 1 - dist 可正确计算
```

**原因：** ChromaDB 返回的 `distances` 是最直接的诊断信号——空列表 = 没数据/embedding 错误，值 > 1 = 度量不匹配（L2 而非 cosine），值 < 1 且很小 = 正常。用 LangChain 封装层拿不到这个字段。向量检索 debug 不需要复杂工具，一个 `print` 就能定位 90% 的问题。

### 26. 智能路由 State key 必须全链路一致

```python
# ❌ 三处 key 各不一样 → LLM 路由决策被静默丢弃
# orchestrator.py prompt:   "required_agents"  (复数)
# orchestrator.py 解析:     data.get("required_agent", ...)  (单数)
# state.py TypedDict:       required_agent: list  (单数)

# ✅ 三处统一为 required_agent
```

**原因：** LLM 按 prompt 格式返回 `required_agents`（复数），解析代码读的是 `required_agent`（单数），取不到 key → fallback 到默认值。表面上代码没报错，但路由永远不生效。排查手段：在 log 里打印 LLM 原始回复，对比实际触发结果。

### 27. 条件路由 + Send API + fan-in join 的坑

```python
# ❌ 条件路由只派发 sql_agent，但 fan-in 要求两个都完成 → Report 永远不会触发
workflow.add_conditional_edges("Orchestrator", dispatch_workers)
workflow.add_edge(["sql_agent", "rag_agent"], "report_agent")

# ✅ 始终派发两个 Agent，不需要的在入口 short-circuit
def dispatch_workers(state):
    return [Send("sql_agent", state), Send("rag_agent", state)]

def rag_agent_node(state):
    if "rag" not in state.get("required_agent", ["sql", "rag"]):
        return {"rag_result": [], "messages": []}  # 立即返回，不浪费 LLM 调用
    # ... 正常 ReAct 循环
```

**原因：** `add_edge(["A", "B"], "C")` 是 barrier — A 和 B 都完成才触发 C。Send API 条件派发时，被跳过的节点永远收不到状态，barrier 永远不满足。Short-circuit 方案保留了 fan-in 语义，且跳过的 Agent 不调用 LLM（零成本）。

### 28. Redis 缓存 + 阈值调整后必须更新 cache key

```python
# ❌ 阈值从 0.7 降到 0.2，但旧 key 里缓存的 [] 还在 → 所有查询全命中缓存返回空
cache_key = f"rag:{query}:{top_k}"

# ✅ 改缓存 key（加版本后缀），旧缓存自动失效
cache_key = f"rag:{query}:{top_k}:v2"
```

**原因：** 缓存 key 不变时，旧的空结果 `[]` 永远不被淘汰（TTL 3600s 内）。改 search 逻辑后必须改 cache key，否则新逻辑被旧缓存"封印"。反过来也一样：改 embedding model、改 collection、改 top_k 策略时都要更新 key。

### 29. DashScopeEmbeddings 的 cosine similarity 实际区间远低于预期

```python
# ❌ 理论值 0.7 不适配 text-embedding-v2 对中文文档的实际分布
if score >= 0.7:  # → 所有结果都被过滤掉

# ✅ 基于实际 distances 打印结果设定阈值
# 打印 query() 返回的 distances → 观察实际区间 → 设定 score_threshold
if score >= 0.2:  # text-embedding-v2 中文相似度实际在 0.05~0.45
```

**原因：** DashScope `text-embedding-v2` 对中文文档的 cosine similarity 集中在 0.05~0.45 区间，远低于"语义相似≈0.7+"的理论预期。设置阈值前必须先 `print` 原始 distances 观察实际分布，否则阈值要么全过滤要么全放行。不同 embedding model 的分数分布差异很大，换模型后要重新校准。

### 30. MemorySaver + 固定 thread_id → 跨查询状态泄漏

```python
# ❌ 固定 thread_id → 上一轮查询的 sql_result/rag_result 残留到下一轮
config = {"configurable": {"thread_id": "user_001"}}
while True:
    result = app.invoke(initial_state, config=config)  # ← 旧状态被覆盖

# ✅ 每次查询用新的 thread_id，状态完全隔离
import uuid
while True:
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = app.invoke(initial_state, config=config)
```

**原因：** LangGraph 的 MemorySaver 以 `thread_id` 为 key 持久化状态。固定 thread_id = 多轮对话共享状态。单轮查询场景下，即使 `initial_state` 里 `sql_result: []`、`rag_result: []`，checkpointer 会用持久化的旧值覆盖。最离谱的表现：用户问"有哪些策略建议？"（纯 RAG），Report 却引用上一个问题的 SQL 数据。

## Git 规范

- **默认分支**: `dev`，**禁止在 master 上直接操作**
- **远端**: `gitee` (码云) + `github` (GitHub)
- **不会推送的文件**: `.env`、`2026-05-26-decision-platform-design.md`、`decision-platform-plan.md`、`CLAUDE.md`、`AGENTS.md`、`one-week-development-plan.md`
- 推送命令: `git push gitee dev && git push github dev`（两个远端都要推）
- **推送默认目标**: 始终推送到 `dev` 分支。除非用户明确要求推送到 `main`，否则不要操作 `main` 分支

## 面试复盘

`decision-platform-plan.md` 中每个 Phase 末尾有 **复盘总结** 区块，每完成一个阶段由开发者填写，作为面试可讲述的项目经验：

1. **完成的功能** — 做了什么，技术栈是什么
2. **遇到的问题 & 解决方案** — 现象 → 排查 → 根因 → 解法
3. **技术决策 & 思考** — 为什么选 A 不选 B，trade-off
4. **面试可讲述点** — 2-3 个具体故事线（场景 → 冲突 → 解决 → 结果）
5. **踩过的坑** — 给未来的自己提个醒

> 每个 Phase 完成时提醒开发者更新对应复盘区块。

## 约束

- DeepSeek 配置通过 `API_KEY` / `BASE_URL` / `MODEL` 环境变量，不硬编码
- Phase 1 全 Mock，不连外部 API（仅 LLM 调用 DeepSeek）✅ 已完成
- Phase 2 接入真实 PostgreSQL（`psycopg2-binary`），本地 `trust` 认证免密码
- 新增业务场景只需在 `mock_data/` 加数据文件，Agent 代码零改动（Phase 1）；Phase 2 起改走 PostgreSQL + ChromaDB
- `log_agent_step` 函数签名为 Phase 2 SSE event 预留，Phase 演进时签名不变
- 上下文文档：设计文档（`2026-05-26-decision-platform-design.md`）和计划文档（`decision-platform-plan.md`）均在项目根目录，仅本地不入 git
