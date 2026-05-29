# Vantage — 企业智能决策中台

基于 LangGraph 多 Agent 协作架构的企业级 AI 决策平台。用自然语言提问，系统自动调度 SQL Agent 查询数据、RAG Agent 检索文档，融合生成带数据表格与来源引用的完整分析报告。

---

## 项目背景

企业决策场景中，回答一个业务问题往往需要同时查询结构化数据（CRM/ERP）和检索非结构化文档（复盘报告、策略手册）。传统方式需要分别找数据分析师和文档，效率低、结论分散。

Vantage 将两条数据线统一接入多 Agent 系统，一个问题即可得到融合了数字与文档依据的完整分析。

---

## 功能演示

```
用户输入：Q2 华东区业绩为什么下滑？

[ORC] 14:23:00 🔍 分析用户问题
[SQL] 14:23:01 ⚡ 执行查询
[RAG] 14:23:01 📚 检索文档
[SQL] 14:23:02 ✅ 查询完成
[RAG] 14:23:03 ✅ 检索完成
[RPT] 14:23:04 📝 生成报告

## 华东区 Q2 业绩分析

### 数据摘要
| 城市 | 2024 Q2 | 2025 Q2 | 同比变化 |
|------|---------|---------|----------|
| 上海 | 1480万  | 1280万  | -13.5%  |
| 杭州 | 680万   | 610万   | -10.3%  |
| 南京 | 510万   | 450万   | -11.8%  |

### 文档来源
- 📄 2025-Q2华东区销售复盘（相关度 0.92）
- 📄 华东市场策略调整建议（相关度 0.85）
- 📄 竞品华东区域动态分析（相关度 0.78）
```

---

## 架构

```
                        START
                          │
                          ▼
                  ┌───────────────┐
                  │  Orchestrator  │
                  │  解析用户问题   │
                  └───────┬───────┘
                          │ Send API 并行分发
            ┌─────────────┴─────────────┐
            ▼                           ▼
      ┌──────────┐               ┌──────────┐
      │ SQL Agent│               │RAG Agent │
      │ ReAct循环 │               │ ReAct循环 │
      │ 查询数据库 │               │ 检索文档  │
      └────┬─────┘               └────┬─────┘
           │                          │
           └───────────┬──────────────┘
                       ▼  (两路到齐才执行)
               ┌──────────────┐
               │ Report Agent  │
               │ 融合生成报告   │
               └──────┬───────┘
                      ▼
                     END
```

**核心设计决策：**

- SQL Agent 和 RAG Agent 通过 Send API 并行执行，互不阻塞
- Report Agent 使用 LangGraph join 语义，等两路数据全部就绪后触发
- `operator.add` reducer 防止并行写回时 State 覆盖
- Orchestrator 输出边预留条件路由扩展点（Phase 2 两行代码升级为智能路由）

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | LangGraph >= 1.2 | StateGraph + ReAct + Send API 并行 + RetryPolicy |
| LLM | DeepSeek API | 兼容 OpenAI 协议，通过 ChatOpenAI 调用 |
| 数据库 | PostgreSQL | 4 表：sales_records / customers / sales_reps / targets |
| 向量检索 | ChromaDB | collection + embedding + query，语义检索 score > 0.7 过滤 |
| Embedding | text-embedding-3-small / sentence-transformers | 优先开源模型节省 API 额度 |
| 缓存 | Redis | 会话管理 + API 响应缓存 + 速率限制 |
| API 服务 | FastAPI + SSE | 流式输出 Agent 执行过程 |
| 前端 | Streamlit | 输入框 → 流式进度 → Markdown 报告渲染 |
| 部署 | Docker Compose | 一键启动，支持云服务器（阿里云 / 腾讯云轻量级） |

---

## 项目结构

```
decision-platform/
├── mock_data/
│   ├── __init__.py          # AVAILABLE_SCENARIOS 场景注册表
│   ├── crm_sales.py         # SQL Agent Mock 数据源
│   └── knowledge_base.py    # RAG Agent Mock 数据源
├── graph/
│   ├── state.py             # AgentState 定义
│   ├── llm.py               # LLM 懒加载单例
│   ├── orchestrator.py      # Orchestrator 节点
│   ├── sql_agent.py         # SQL Agent — ReAct 循环
│   ├── rag_agent.py         # RAG Agent — ReAct 循环
│   ├── report_agent.py      # Report Agent — 纯格式化 + 降级模板
│   └── builder.py           # LangGraph 图构建 + RetryPolicy
├── tools/
│   ├── sql_tools.py         # execute_query
│   └── rag_tools.py         # search_docs
├── utils/
│   └── logger.py            # log_agent_step 结构化终端输出
├── main.py                  # 入口
├── pyproject.toml
└── .env
```

---

## 快速开始

**环境要求：** Python 3.10+

**1. 安装依赖**

```bash
cd decision-platform && uv sync
```

**2. 配置环境变量**

在 `decision-platform/` 目录下创建 `.env`：

```
API_KEY=your_deepseek_api_key
BASE_URL=https://api.deepseek.com
MODEL=deepseek-chat
```

**3. 运行终端 Demo（Phase 1）**

```bash
uv run python main.py
```

**4. 启动完整服务（Phase 4）**

```bash
docker compose up -d
```

---

## 错误处理

| 场景 | 策略 |
|------|------|
| LLM 调用失败（Orchestrator/SQL/RAG） | RetryPolicy 自动重试 3 次（指数退避，backoff_factor=2.0） |
| SQL 查询异常 | 返回错误标记，报告标注「数据暂不可用」 |
| RAG 检索无结果 | 返回空列表，报告标注「未找到相关文档」 |
| 双路同时失败 | 前置检查，直接返回明确错误提示 |
| Report LLM 调用失败 | 节点内部重试 2 次 → 降级为模板拼接，保证有输出 |

---

## 演进路线

```
Phase 1  Mock 数据 + LangGraph 全链路跑通（终端 Demo，Week 1–2）
         ├─ Mock 数据层 + 工具层 + AgentState + 日志
         └─ SQL/RAG Agent ReAct 循环 + Graph 连线 + 端到端联调

Phase 2  Redis 缓存 + 会话管理 + 智能路由（Week 3–4）
         ├─ Redis 集成：SQL/RAG 工具接缓存 + 会话上下文 + 速率限制
         └─ 智能路由：add_conditional_edges 替换硬编码全并行

Phase 3  真实数据接入 + 向量检索（Week 5–6）
         ├─ PostgreSQL：4 表 Schema + Text-to-SQL + 1000+ 条测试数据
         └─ ChromaDB：真实 embedding 存入 + search_docs 升级 + score 阈值调优

Phase 4  部署 + 前端 + 生产化（Week 7–8）
         ├─ FastAPI + SSE 流式 + Streamlit 前端 + 多用户会话隔离
         └─ Docker Compose 云部署 + 权限系统 + Token 日志 + 链路追踪
```

每个 Phase 工具层接口不变，Graph 层零改动。

---

## 新增业务场景

在 `mock_data/` 中各加一个同名 key，更新注册表，无需改动任何 Agent 代码：

```python
# mock_data/__init__.py
AVAILABLE_SCENARIOS = ["q2_east_china", "customer_churn"]  # 加这里

# mock_data/crm_sales.py
SCENARIOS = {
    "q2_east_china": {...},
    "customer_churn": {...},   # 加这里
}

# mock_data/knowledge_base.py
SCENARIOS = {
    "q2_east_china": [...],
    "customer_churn": [...],   # 加这里
}
```

---

## 依赖

```
langgraph >= 1.2
langchain >= 1.3
langchain-openai >= 1.2
python-dotenv >= 1.0
```
