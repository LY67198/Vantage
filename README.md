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
- Orchestrator 输出边预留条件路由扩展点（Phase 3 两行代码升级为智能路由）

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | LangGraph >= 1.2 | StateGraph + ReAct + Send API 并行 + RetryPolicy |
| LLM | DeepSeek API | 兼容 OpenAI 协议，通过 ChatOpenAI 调用 |
| 数据库 | PostgreSQL | sales_records 等业务表 |
| ORM | SQLAlchemy + Alembic | 模型定义 + 数据库迁移管理 |
| 向量检索 | ChromaDB | 余弦距离语义检索 |
| Embedding | DashScope text-embedding-v2 | 中文语义向量化 |
| 缓存 | Redis | SQL 结果缓存 + RAG 查询缓存 |
| 异步任务 | Celery | 导出任务异步执行 + 定时清理过期文件 |
| API 服务 | FastAPI + SSE | RESTful API + 流式输出 + Swagger 自动文档 |
| 鉴权 | JWT | 注册/登录/Token 刷新 + RBAC（admin/user） |
| 前端 | Vue 3 + Element Plus | 输入框 → 流式进度 → Markdown 报告渲染 |
| 导出 | ReportLab + openpyxl | PDF + Excel 报告导出 |
| 日志 | structlog | 结构化日志 + trace_id 链路追踪 |
| 测试 | pytest | 单元测试 + 集成测试，核心路径覆盖 60%+ |
| 部署 | Docker Compose | 开发/生产分离，一键启动 4 服务 |

---

## 项目结构

```
Vantage/
├── decision-platform/         # Python 后端
├── frontend/                  # Vue 3 + Element Plus 前端
│   ├── src/views/             # Login.vue / Query.vue
│   ├── src/components/        # QueryInput / AgentProgress / ReportView
│   └── src/router/            # 路由 + JWT 守卫
└── docs/
```

### 后端目录详情

```
decision-platform/
├── api/                     # Phase 4 — FastAPI 层
│   ├── app.py               # FastAPI 实例 + lifespan（启动/关闭）
│   ├── middleware/
│   │   └── __init__.py      # JWT（Day 32）+ tracing（Day 38）预留
│   ├── routes/
│   │   └── query.py         # POST /query (SSE 流式), GET /health ✅
│   └── schemas/
│       └── query.py         # QueryRequest ✅
├── graph/                   # ☑ 不动（4 个 Agent + builder + state）
│   ├── state.py
│   ├── llm.py
│   ├── orchestrator.py
│   ├── sql_agent.py
│   ├── rag_agent.py
│   ├── report_agent.py
│   └── builder.py
├── tools/                   # ☑ 不动（sql_tools + rag_tools）
│   ├── sql_tools.py
│   └── rag_tools.py
├── utils/
│   ├── logger.py            # 终端彩色日志 + SSE 事件推送 ✅
│   ├── schema.py
│   └── chroma_client.py
├── main.py                  # ☑ 保留，终端交互入口
├── pyproject.toml
└── .env.example             # Day 39 创建
```

**📋 后续 Days 新增（按计划）：**

```
api/
├── middleware/auth.py       # Day 32 — JWT 验证依赖
├── routes/
│   ├── auth.py              # Day 32 — 注册/登录/刷新
│   └── export.py            # Day 34 — 导出 + 下载
└── schemas/
    ├── auth.py              # Day 32
    └── export.py            # Day 34
tasks/                       # Day 34 — Celery 异步导出
services/                    # Day 32 — 业务逻辑层
models/                      # Day 32 — SQLAlchemy ORM
migrations/                  # Day 36 — Alembic
tests/                       # Day 37 — pytest
```

---

## 快速开始

**环境要求：** Python 3.10+ / Docker Desktop

**1. 克隆项目**

```bash
git clone <repo-url> && cd Vantage/decision-platform
```

**2. 配置环境变量**

```bash
cp .env.example .env
# 编辑 .env，填入 API_KEY 等必要配置
```

**.env 必要变量：**

| 变量 | 说明 |
|------|------|
| `API_KEY` | DeepSeek API Key |
| `BASE_URL` | API 地址（默认 https://api.deepseek.com） |
| `MODEL` | 模型名（默认 deepseek-chat） |
| `EMBEDDING_API_KEY` | DashScope API Key（阿里云） |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` | PostgreSQL 连接 |
| `REDIS_HOST` / `REDIS_PORT` | Redis 连接 |
| `JWT_SECRET` | JWT 签名密钥 |

**3. 一键启动（Docker Compose）**

```bash
# 开发环境（热重载 + 源码挂载）
docker compose up -d

# 生产环境
docker compose -f docker-compose.prod.yml up -d
```

**4. 初始化数据库**

```bash
# 运行数据库迁移
docker compose exec app alembic upgrade head

# 导入种子数据
docker compose exec app python scripts/seed_data.py
docker compose exec app python scripts/init_chroma.py
```

**5. 访问服务**

| 服务 | 地址 |
|------|------|
| API 文档 (Swagger) | http://localhost:8000/docs |
| Vue 3 前端 | http://localhost:5173 |
| 健康检查 | http://localhost:8000/health |

**6. 测试 SSE 流式查询**

```bash
curl -N -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question":"华东区Q2各城市营收是多少？"}'
# 预期：逐步推送 agent_step 事件（ORC → SQL → RAG → RPT）→ done
```

**7. 终端调试模式（保留）**

```bash
uv run python main.py
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
Phase 1  Mock 数据 + LangGraph 全链路跑通（Week 1–2）✅
         ├─ Mock 数据层 + 工具层 + AgentState + 日志
         └─ SQL/RAG Agent ReAct 循环 + Graph 连线 + 端到端联调

Phase 2  真实数据接入 + 向量检索（Week 3–4）✅
         ├─ PostgreSQL：真实 DB 查询 + Schema 注入 + Text-to-SQL
         └─ ChromaDB：向量检索 + DashScopeEmbeddings + score 阈值校准

Phase 3  Redis 缓存 + 智能路由（Week 5–6）✅
         ├─ Redis 集成：SQL/RAG 工具缓存 + 缓存 key 版本化
         └─ 智能路由：LLM 条件路由 + Agent short-circuit + uuid 隔离

Phase 4  工程化落地（Week 7–8）
         ├─ Week 7：FastAPI + Swagger ✅ + SSE 流式 ✅ + JWT + Vue 3 + PDF/Excel + Docker
         └─ Week 8：Alembic + pytest + structlog + README + 部署上云
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
celery[redis] >= 5.4
redis
```
