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

──────────────────────────────────────────────────
[ORC] 14:23:00 🔍 分析用户问题
识别到需要: SQL查询(销售数据) + 文档检索(历史策略)

──────────────────────────────────────────────────
[SQL] 14:23:01 ⚡ 执行查询
SELECT region, revenue, yoy_change FROM sales WHERE region='华东'

──────────────────────────────────────────────────
[RAG] 14:23:01 📚 检索文档
找到 3 份相关文档 (score > 0.7)

──────────────────────────────────────────────────
[SQL] 14:23:02 ✅ 查询完成
华东区 Q2 营收 2340万，同比 -12.3%

──────────────────────────────────────────────────
[RAG] 14:23:03 ✅ 检索完成
Q2华东复盘 / 华东策略建议 / 竞品动态分析

──────────────────────────────────────────────────
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
- Orchestrator 输出边预留条件路由扩展点，两行代码升级为智能路由

---

## 技术栈

| 层级 | 技术 |
|------|------|
| Agent 框架 | LangGraph |
| LLM | DeepSeek API（兼容 OpenAI 协议） |
| 向量检索 | ChromaDB |
| 数据库 | PostgreSQL |
| 缓存 | Redis |
| API 服务 | FastAPI + SSE 流式输出 |
| 前端 | Streamlit |
| 部署 | Docker Compose |

---

## 项目结构

```
vantage/
├── mock_data/
│   ├── __init__.py          # AVAILABLE_SCENARIOS 场景注册表
│   ├── crm_sales.py         # SQL Agent Mock 数据源
│   └── knowledge_base.py    # RAG Agent Mock 数据源
├── graph/
│   ├── state.py             # AgentState 定义
│   ├── orchestrator.py      # Orchestrator 节点
│   ├── sql_agent.py         # SQL Agent — ReAct 循环
│   ├── rag_agent.py         # RAG Agent — ReAct 循环
│   ├── report_agent.py      # Report Agent — 纯格式化
│   └── builder.py           # LangGraph 图构建
├── tools/
│   ├── sql_tools.py         # execute_query
│   └── rag_tools.py         # search_docs
├── utils/
│   └── logger.py            # log_agent_step 结构化终端输出
├── main.py                  # 入口
├── pyproject.toml
└── .env.example
```

---

## 快速开始

**环境要求：** Python 3.11+，Docker

**1. 克隆项目**

```bash
git clone https://github.com/yourname/vantage.git
cd vantage
```

**2. 安装依赖**

```bash
pip install -e .
```

**3. 配置环境变量**

```bash
cp .env.example .env
```

编辑 `.env`：

```
API_KEY=your_deepseek_api_key
BASE_URL=https://api.deepseek.com
MODEL=deepseek-chat
```

**4. 启动服务（Phase 4）**

```bash
docker compose up -d
```

**5. 运行终端 Demo（Phase 1）**

```bash
python main.py
```

---

## 错误处理

| 场景 | 策略 |
|------|------|
| LLM 调用失败 | RetryPolicy 自动重试 3 次（指数退避） |
| SQL 查询异常 | 返回错误标记，报告标注「数据暂不可用」 |
| RAG 检索无结果 | 返回空列表，报告标注「未找到相关文档」 |
| 双路同时失败 | 前置检查，直接返回明确错误提示 |
| Report 生成失败 | 降级为模板拼接，保证有输出 |

---

## 演进路线

```
Phase 1  Mock 数据 + LangGraph 全链路跑通（终端 Demo）
Phase 2  Redis 缓存 + 会话管理 + 智能路由
Phase 3  PostgreSQL 真实数据 + ChromaDB 向量检索
Phase 4  FastAPI + Streamlit + Docker 云端部署
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
langgraph >= 1.0
langchain >= 0.3
langchain-openai
chromadb
redis
fastapi
streamlit
python-dotenv
```
