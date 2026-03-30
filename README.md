# 🚀 Web3 Intelligent Investment Analysis System (Web3 智能投研 Agent)

基于 **FastAPI + LangGraph + PostgreSQL** 构建的企业级全异步 Web3 自动化投研流水线。系统能够自动抓取行业快讯，通过大模型进行基于思维链 (CoT) 的实体提取，结合真实 Binance 盘面数据与 RAG 深度研报检索，最终输出高置信度的结构化投资策略。

## ✨ 核心工程亮点 (Core Highlights)

* **⚡ 全链路异步架构 (Asynchronous Pipeline)**
    * 采用 `FastAPI` 作为高吞吐接入层，结合 `RabbitMQ` 消息队列实现请求与耗时 AI 推理的彻底解耦。
    * 底层采用 `asyncpg` 和 `httpx`，完美避开 I/O 阻塞，保障高并发场景下的接口高可用性。
* **🧠 结构化思维链 (Structured CoT) 治理幻觉**
    * **痛点**：传统 LLM 在提取加密货币实体时极易混淆机构名与项目名（如将 a16z 误认为代币）。
    * **解法**：深入重构 Pydantic Schema，强制模型在输出标准 `["SOL", "BTC"]` 数组前，必须先行输出 `thinking_process` 字段。利用自回归特性完成“扫描 -> 甄别 -> 映射”的标准 SOP，将实体提取准确率提升至 99% 以上。
* **🔄 LangGraph 状态机编排 (State-Driven Workflow)**
    * 摒弃脆弱的线性 Chain，设计严格的 `AnalysisState` 全局 TypedDict。
    * 实现动态路由：在“价值初筛”节点引入条件边 (Conditional Edges)，无投资价值的噪音数据直接路由至 `END` 熔断，极大节省 Token 成本与算力。
* **📈 真实业务数据兜底 (Fact-Grounded Reasoning)**
    * 拒绝“大模型纸上谈兵”。系统在提取代币符号后，自动发起请求至 Binance API 抓取实时 24h 涨跌幅与量价数据，强制 LLM 结合真实盘面给出 `buy / sell / hold` 的枚举交易指令。

## 🏗️ 架构拓扑 (Architecture)

1. **[接入层]** Frontend -> `POST /analyze` (FastAPI) -> RabbitMQ
2. **[控制层]** Worker Process 消费队列 -> 初始化 `AnalysisState`
3. **[AI 分析层 - LangGraph]**
   - Node 1: 价值判定 & 情绪分析 (动态路由拦截)
   - Node 2: 核心要素提取 (Structured CoT)
   - Node 2.5: RAG 知识检索 (pgvector 检索白皮书/研报)
   - Node 3: Binance API 行情数据注入
   - Node 4: 基金经理终局决策 (综合基本面与技术面)
