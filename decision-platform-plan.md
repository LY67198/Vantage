# 企业智能决策中台 — 项目实施计划

## 总览

| 阶段 | 周期 | 核心目标 | 交付物 |
|------|------|----------|--------|
| Phase 1 | Week 1–2 | Mock 数据 + LangGraph 全链路跑通 | 可运行的终端 Demo |
| Phase 2 | Week 3–4 | Redis 缓存 + 会话管理 + 智能路由 | 带缓存的 API 服务 |
| Phase 3 | Week 5–6 | 真实 DB + Text-to-SQL + 向量检索 | 接真实数据的完整系统 |
| Phase 4 | Week 7–8 | 部署 + 前端 + 权限 + 可观测性 | 可演示的生产级应用 |

---

## Phase 1：Mock + 链路跑通（Week 1–2）

> 目标：所有节点跑通，终端看到完整的 Orchestrator → SQL/RAG 并行 → Report 输出

### Week 1：数据层 + 工具层

| 天 | 任务 | 文件 | 完成标志 |
|----|------|------|----------|
| Day 1 | 项目初始化，配置依赖 | `pyproject.toml` / `.env` | `pip install` 无报错 |
| Day 1 | Mock 数据编写 | `mock_data/crm_sales.py` | `SCENARIOS["q2_east_china"]` 数据完整 |
| Day 2 | Mock 文档编写 | `mock_data/knowledge_base.py` | 3 份文档，score 字段就位 |
| Day 2 | `__init__.py` 注册 + 启动校验 | `mock_data/__init__.py` | assert 检测 key 不一致时报错退出 |
| Day 3 | AgentState 定义 | `graph/state.py` | TypedDict 字段齐全，reducer 标注正确 |
| Day 3 | 日志工具 | `utils/logger.py` | 终端彩色输出，时间戳正常 |
| Day 4 | SQL 工具实现 | `tools/sql_tools.py` | `execute_query()` 单独调用返回正确数据 |
| Day 5 | RAG 工具实现 | `tools/rag_tools.py` | `search_docs()` 单独调用返回文档列表 |

**Week 1 验收：** 两个工具函数独立调用均返回预期结果，终端日志格式正确。

---

### Week 2：Agent 层 + Graph 连线

| 天 | 任务 | 文件 | 完成标志 |
|----|------|------|----------|
| Day 6 | SQL Agent ReAct 循环 | `graph/sql_agent.py` | 单独运行，终端打印查询结果 |
| Day 7 | RAG Agent ReAct 循环 | `graph/rag_agent.py` | 单独运行，终端打印检索结果 |
| Day 8 | Orchestrator 节点 | `graph/orchestrator.py` | LLM 解析问题，`messages` 写入正确 |
| Day 8 | Report Agent + 降级模板 | `graph/report_agent.py` | 双路失败时降级输出可读报告 |
| Day 9 | Graph 连线 + RetryPolicy | `graph/builder.py` | 图结构正确，并行边 + join 边到位 |
| Day 10 | 入口 + 端到端联调 | `main.py` | 输入问题，终端完整输出三路日志 + Markdown 报告 |

**Week 2 验收：**
```
输入：「Q2 华东区业绩为什么下滑？」

终端输出：
[ORC] 14:23:00 🔍 分析用户问题
[SQL] 14:23:01 ⚡ 执行查询
[RAG] 14:23:01 📚 检索文档
[SQL] 14:23:02 ✅ 查询完成
[RAG] 14:23:03 ✅ 检索完成
[RPT] 14:23:04 📝 生成报告
## 华东区 Q2 业绩分析...
```

---

## Phase 2：Redis + 智能路由（Week 3–4）

> 目标：引入 Redis 缓存、会话管理，Orchestrator 升级为智能路由

### Week 3：Redis 集成

| 天      | 任务               | 说明                                        |
| ------ | ---------------- | ----------------------------------------- |
| Day 11 | Redis 环境搭建       | Docker 启动 Redis，连接验证                      |
| Day 12 | SQL 工具接 Redis 缓存 | `execute_query` 内部：先查缓存 → 未命中查 Mock → 写缓存 |
| Day 13 | RAG 工具接 Redis 缓存 | `search_docs` 同上，embedding 暂用 Mock 向量     |
| Day 14 | 会话管理             | 同一 session_id 的多轮对话共享上下文                  |
| Day 15 | API 响应缓存 + 速率限制  | 相同问题直接返回缓存结果，限制并发调用                       |

### Week 4：智能路由 + 扩展场景

| 天 | 任务 | 说明 |
|----|------|------|
| Day 16 | Orchestrator 升级为智能路由 | `add_conditional_edges` 替换硬编码全并行 |
| Day 17 | `required_agents` 字段注入 State | Orchestrator 判断后写入，route 函数读取 |
| Day 18 | 新增第二个 Mock 场景 | `mock_data/` 加 `customer_churn` 场景，零代码改动验证 |
| Day 19–20 | 联调 + 压测 | 多问题连续请求，验证缓存命中率和路由准确性 |

**Week 4 验收：**
- 纯数据问题只触发 SQL Agent，纯文档问题只触发 RAG Agent
- 相同问题第二次请求走缓存，响应时间 < 100ms
- 新场景加数据文件后立即可用，不改图代码

---

## Phase 3：真实数据接入（Week 5–6）

> 目标：Mock 数据逐步替换为真实 DB 和向量检索，工具接口不变

### Week 5：数据库接入

| 天 | 任务 | 说明 |
|----|------|------|
| Day 21 | PostgreSQL 环境 + Schema 设计 | 建 4 张表：sales_records / customers / sales_reps / targets |
| Day 22 | 导入测试数据 | 生成 1000+ 条模拟销售记录 |
| Day 23 | Text-to-SQL 工具升级 | `execute_query` 从 Mock → 真实 DB 查询，接口不变 |
| Day 24 | Schema 管理 | 自动注入表结构到 LLM prompt，提升 SQL 生成准确率 |
| Day 25 | SQL Agent 联调 | 验证复杂查询（JOIN / 聚合 / 窗口函数）正确率 |

### Week 6：真实向量数据库接入 ⭐ 求职补强点

| 天 | 任务 | 说明 |
|----|------|------|
| Day 26 | ChromaDB 环境搭建 | 本地安装，理解 collection / embedding / query 三个核心概念 |
| Day 27 | 文档写入 ChromaDB | 把 Mock 文档转成真实 embedding 存入，选用 `text-embedding-3-small` 或开源模型 |
| Day 28 | `search_docs` 工具升级 | Mock → ChromaDB 向量检索，接口不变，score 字段由库自动返回 |
| Day 29 | RAG Agent 联调 + 阈值调优 | 验证检索相关性，score > 0.7 过滤，对比 Mock 阶段结果 |
| Day 30 | 端到端联调 | 真实问题 → 真实 DB + 真实向量检索 → 完整报告，验收质量 |

**Week 6 验收：**
- ChromaDB 存有真实 embedding，`search_docs` 返回语义相关文档
- RAG Agent 检索返回相关文档，score > 0.7 过滤有效
- SQL Agent 生成有效查询并返回真实数据
- 完整链路响应时间 < 10s
- **面试可说**：「用 ChromaDB 实现了语义检索，对比过 chunk 大小对检索质量的影响」

---

## Phase 4：部署 + 前端 + 生产化（Week 7–8）

> 目标：容器化部署，Streamlit 前端，权限系统，可观测性

### Week 7：FastAPI + Streamlit + 云部署 ⭐ 求职补强点

| 天 | 任务 | 说明 |
|----|------|------|
| Day 31 | FastAPI 封装 | `POST /query` 接口，`log_agent_step` 改为 SSE event |
| Day 32 | Streamlit 前端 | 输入框 → 流式展示 Agent 进度 → Markdown 报告渲染 |
| Day 33 | 多用户会话隔离 | session_id 绑定用户，State 不串 |
| Day 34 | 权限系统基础 | 用户角色 → 可查询数据范围（行级权限） |
| Day 35 | Docker Compose + 云服务器部署 | 本地 Docker Compose 跑通 → 推到云服务器（阿里云 / 腾讯云 轻量级 2核4G）→ 外网可访问 |

**云部署要点：**
- 域名 + HTTPS 不是必须的，有公网 IP 能访问就算完成
- 云服务器选最便宜的轻量级即可，Demo 用不需要高配
- **面试可说**：「项目已部署在公网，可以实时演示」——这句话价值远超纸上描述

### Week 8：可观测性 + 收尾

| 天 | 任务 | 说明 |
|----|------|------|
| Day 36 | Middleware 接入 | Token 消耗日志，每次 LLM 调用记录 cost |
| Day 37 | 链路追踪 | Agent 调用链完整记录，出错可定位到具体节点 |
| Day 38 | 层级 Supervisor 预研 | Orchestrator 上层加 Master，为多业务域扩展铺路 |
| Day 39 | 文档整理 + README | 部署文档、API 文档、架构图更新 |
| Day 40 | Demo 演示准备 | 3 个典型问题 + 完整演示脚本 |

**Week 8 验收（最终）：**
- Docker Compose 一键启动，5 分钟内可 Demo
- Streamlit 界面流式展示 Agent 执行过程
- 项目已部署公网，面试时可实时演示
- Token 消耗可查，链路可追踪
- README 包含完整部署步骤

---

## 关键路径 & 风险

| 风险点                   | 发生阶段     | 应对策略                                        |
| --------------------- | -------- | ------------------------------------------- |
| DeepSeek API 限流       | Week 1–2 | RetryPolicy 已配置；本地 Mock 不依赖 API             |
| Text-to-SQL 准确率低      | Week 5   | 先用简单查询验证，Schema 注入 prompt 提升准确率             |
| 向量检索相关性差              | Week 6   | score 阈值可调；Mock 阶段已验证 RAG 链路逻辑              |
| ChromaDB embedding 成本 | Week 6   | 优先用开源模型（`sentence-transformers`），不消耗 API 额度 |
| 云服务器网络不稳定             | Week 7   | DeepSeek API 在国内访问稳定，优先选国内云厂商节点             |
| LangGraph 版本兼容        | 全程       | 锁定版本号在 `pyproject.toml`，升级前查 changelog      |

---

## LangGraph 知识点落地时间线

```
Week 1  StateGraph + TypedDict + add_messages reducer
Week 2  bind_tools + ReAct 循环 + Send API 并行 + RetryPolicy
Week 3  Redis 集成（工具层，不影响 Graph）
Week 4  add_conditional_edges + 智能路由
Week 5  真实工具替换（接口不变，Graph 零改动）
Week 6  ChromaDB 向量检索（⭐ 求职补强点一）
Week 7  Middleware + SSE 流式输出 + 云服务器部署（⭐ 求职补强点二）
Week 8  层级 Supervisor 预研
```

> 每个 Phase 结束时，已学的 LangGraph 知识点都有对应的真实代码落地，不是纸上练兵。
