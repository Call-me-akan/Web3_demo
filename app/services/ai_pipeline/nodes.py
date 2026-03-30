import logging
import asyncio
import random
import json
from sqlalchemy import select
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
# from langchain_openai import ChatOpenAI
from app.services.ai_pipeline.state import AnalysisState, ValueJudgmentOutput, TokenExtractionOutput, FinalDecisionOutput
from app.services.ai_pipeline.llm_service import llm_service,get_embdding
from app.db.session import AsyncSessionLocal
from app.models.Knowledge import KnowledgeModel
from httpx import AsyncClient


logger = logging.getLogger(__name__)

llm = llm_service.llm
# 核心魔法：将普通大模型绑定 Pydantic 规约，变成一个强制输出结构化数据的“分析机器”
structured_llm = llm.with_structured_output(ValueJudgmentOutput)
extractor_llm = llm.with_structured_output(TokenExtractionOutput)

decision_llm = llm.with_structured_output(FinalDecisionOutput)
# ==========================================
# 1. 定义提示词模板 (Prompt Engineering)
# ==========================================
# 好的系统提示词(System Prompt)是 AI Agent 的灵魂。我们要给它设定身份、任务和明确的边界。
system_prompt = """你是一位顶级的 Web3 投资分析师。
你的任务是阅读给定的行业快讯，并严格客观地判断其是否具有真实的投资价值或对加密市场有实质性影响。

【判断标准指南】：
- 有价值 (is_valuable=True)：必须涉及核心基本面变化。例如：主网上线、代币经济学(Tokenomics)更改、巨额机构融资、重大黑客攻击/资产被盗、顶级传统机构合作、各国合规与监管的重大法案落地等。
- 无价值 (is_valuable=False)：日常噪音。例如：毫无实质内容的 AMA 预告、KOL 主观喊单、常规的网页 UI 更新、某个冷门项目发推特打招呼等。
请根据上述标准进行深度推理，并严格按照要求的格式输出你的分析结果。"""

system_prompt_extract = """
你是一个极其严谨的 Web3 交易员。你的任务是从快讯中提取【核心项目名称】以及【可在币安直接交易的加密货币标准符号】。。

【核心工作流】（你必须在 thinking_process 中展示此过程）：
1. 扫描实体：找出文中所有的专有名词。
2. 身份甄别（极度重要）：
   - 它是传统机构、资本方或媒体吗？(如 a16z, Glassnode, CoinDesk, Visa) -> [排除]
   - 它是技术术语或生态统称吗？(如 DeFi, NFT, L2, Solana 生态) -> [排除]
   - 它是具体的 Web3 项目吗？(如 Bitcoin, Ethereum, Solana) -> [进入第3步]
3. 代码映射：将保留下来的项目名，强制转换为其在交易所的【大写标准交易代码】。
   - 示例映射：比特币/Bitcoin -> BTC；以太坊/Ethereum -> ETH；Solana -> SOL。

【绝对格式高压线】：
- 提取的结果必须是纯大写字母（如 BTC, ETH, PEPE）。
- 绝对禁止包含中文、空格、小写字母或附加词汇（严禁出现 "Solana 基金会", "Bitcoin Vector" 等无效格式）。
- 如果文中没有任何可以直接炒作交易的代币，你的 tokens 字段必须返回空列表 []。宁可漏掉，绝不乱加！
"""




system_prompt_decision = """你是一位顶级的 Web3 基金经理和量化交易策略师。
你的任务是结合【行业快讯基本面】和【当前盘面市场数据】，给出最终的投资动作建议。

【决策原则】：
- buy (买入): 属于重大利好，且当前市场数据（如有）未出现极端的暴涨泡沫，有建仓空间。
- sell (卖出): 属于重大利空（如黑客攻击、团队被捕），或面临严重抛压风险。
- hold (观望): 消息偏中性，或利好/利空被当前盘面数据对冲（例如：虽是利好，但24小时涨幅已超 50%，追高风险极大）。
- ignore (忽略): 纯粹的噪音，没有实际交易价值。

请结合所有信息进行严密的逻辑推演，并返回结构化决策。"""


#==========================================

prompt_extractor = ChatPromptTemplate.from_messages([
    ("system", system_prompt_extract),    
    ("human", "请从以下快讯内容中抽取核心要素：\n{news_content}")
    ])

# 组装聊天模板
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "需要分析的快讯内容如下：\n{news_content}")
])

prompt_decision = ChatPromptTemplate.from_messages([
    ("system", system_prompt_decision),
    ("human", "【快讯原文】:\n{news_content}\n\n【相关代币】:\n{extracted_tokens}\n\n【实时市场数据】:\n{market_data}\n\n【深度知识库参考】:\n{retrieved_knowledge}") # <--- 新增这行
])
decision_chain = prompt_decision | decision_llm


# ============将提示词和大模型串联成一个完整的 Chain (链)==================
value_judgment_chain = prompt | structured_llm
extract_chain = prompt_extractor | extractor_llm



# ==========================================
# 2. 编写图节点函数 (Node Function)
# ==========================================
async def analyze_value_node(state: AnalysisState) -> dict:
    """
    节点 1：价值判断节点
    输入：当前状态 (包含 news_content)
    输出：更新后的状态字典
    """
    logger.info(f"--- 节点 1：开始分析快讯价值 | ID: {state['news_id']} ---")
    content = state["news_content"]

    try:
        # 执行调用，result 的类型会被完美推导为 ValueJudgmentOutput 对象
        result: ValueJudgmentOutput = await value_judgment_chain.ainvoke({"news_content": content})

        logger.info(f"价值判断完成: {'有投资价值' if result.is_valuable else '无投资价值'} | 情绪: {result.sentiment}")

        # 重点：我们返回一个字典，LangGraph 会自动用它来合并/覆盖 AnalysisState 中对应的字段
        return {
            "is_valuable": result.is_valuable,
            "sentiment": result.sentiment,
            "judgment_reason": result.reason
        }
    except Exception as e:
        logger.error(f"大模型价值分析节点发生异常: {e}")
        # 企业级防御性编程：如果 API 超时或大模型抽风，决不能让整个程序死掉。
        # 这里进行降级处理（Fallback），默认当作无价值新闻丢弃。
        return {
            "is_valuable": False,
            "sentiment": "neutral",
            "judgment_reason": f"AI 分析失败，执行自动降级拦截。错误详情: {str(e)}"
        }

async def extract_token_node(state: AnalysisState) ->dict:
    """
    节点 2：核心要素与代币抽取
    """
    logger.info(f"--- 节点2：开始抽取核心要素 | ID: {state['news_id']} ---")
    content = state["news_content"]

    try:
        result: TokenExtractionOutput = await extract_chain.ainvoke({"news_content": content})
        logger.info(f"要素抽取完成: 项目: {result.project_name}  | 代币: {', '.join(result.tokens)}")
        return {
            "project_name": result.project_name,
            "extracted_tokens": result.tokens
        }
    except Exception as e:
        logger.error(f"大模型要素抽取节点发生异常: {e}")
        # 企业级防御性编程：如果 API 超时或大模型抽风，决不能让整个程序死掉。
        # 这里进行降级处理（Fallback），默认当作无价值新闻丢弃。
        return {
            "project_name": "Unknown",
            "event_type": "Unknown",
            "extracted_tokens": []
        }

async def retrieve_knowledge_node(state: AnalysisState)->dict:
    """
    节点 2.5：RAG 知识检索节点
    """
    project_name = state.get("project_name")
    news_content = state.get("news_content")

    logger.info(f"--- 节点 2.5：开始检索 [{project_name}] 的背景知识 ---")
    
    if not project_name or project_name == "Unknown":
        logger.info(">>> 未提取到明确项目名，跳过知识检索。")
        return {"retrieved_knowledge": ""}
    
    try:
        # 1. 把当前快讯内容（或项目名）转化为向量，用来去库里匹配
        # 这里为了匹配精度，我们用 "项目名 + 快讯内容" 去生成查询向量
        query_text = f"项目：{project_name}。相关信息：{news_content}"
        query_vector = await get_embdding(query_text)

        # 2. 向量相似度搜索 (Cosine Distance)
        async with AsyncSessionLocal() as db:
            # <=> 是 pgvector 的余弦距离运算符，距离越小越相似
            stmt = (
                select(KnowledgeModel)
                .filter(KnowledgeModel.project_name == project_name )# 先用项目名做硬过滤，极大提升速度
                .order_by(KnowledgeModel.embedding.cosine_distance(query_vector))
                .limit(3)
            )
            result = await db.execute(stmt)
            docs = result.scalars().all()

            if docs:
                knowledge_text = "\n\n".join(#你在给大模型准备上下文（Context）时，使用双换行来区分“指令”、“参考资料”和“用户问题”，让模型看得更清楚，而不至于把新闻内容和你的指令搞混
                    [f"[参考资料{i+1}:{doc.content}]"
                      for i ,doc in enumerate(docs)])
                logger.info(f">>> 成功检索到 {len(docs)} 条强相关背景知识！")
                return {"retrieved_knowledge":knowledge_text}
            else:
                logger.info(">>> 知识库中未找到相关资料。")
                return {"retrieved_knowledge": ""}
    except Exception as e:
        logger.error(f"❌ 知识检索失败: {e}")
        return {"retrieved_knowledge": ""}
def router_judgment(state: AnalysisState) -> str:
    """
    节点 3：路由判断节点
    根据节点 1 的价值判断结果，决定下一步流转路径。
    输入：当前状态 (包含 is_valuable)
    输出：下一个节点的名称
    """
    logger.info(f"--- 节点3：路由判断 | ID: {state['news_id']} ---")
# 从状态机中获取节点 1 的判断结果
    is_valuable = state.get("is_valuable", False)
    
    if is_valuable:
        logger.info(">>> 路由决策：快讯有价值，放行至 [要素提取节点]")
        return "extract_token"
    else:
        logger.info(">>> 路由决策：快讯无价值，终止分析流程")
        return END
    
async def fetch_market_data_node(state: AnalysisState) ->dict:
    """
    节点 3：获取实时市场数据
    """
    logger.info(f"--- 节点 3：开始获取实时市场数据 | ID: {state['news_id']} ---")
    tokens = state.get("extracted_tokens")

    if not tokens:
        logger.info(">>> 没有提取到关联代币，跳过市场数据查询。")
        return {"market_data": {}}

    market_info = {}
    # 遍历代币列表，模拟调用外部行情 API
    # for token in tokens:
    #     # 模拟网络延迟
    #     await asyncio.sleep(0.5) 
    #     # 伪造一些逼真的盘面数据
    #     market_info[token] = {
    #         "current_price": round(random.uniform(10, 500), 2),
    #         "24h_change_percent": round(random.uniform(-15, 20), 2),
    #         "volume_24h": "1.2B"
    #     }
    async with AsyncClient() as client:
        for token in tokens:
            # 细节：大模型提取的可能是 "SOL" 或 "eth"，我们需要统一转大写，并拼上 "USDT" 交易对
            symbol = f"{token.upper()}USDT"
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            try:
                # 设置 10 秒超时，防止 API 接口卡死拖垮整个流水线
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    # 提取核心数据并保留合理的小数位
                    market_info[token] = {
                        "current_price": round(float(data["lastPrice"]), 4),
                        "24h_change_percent": round(float(data["priceChangePercent"]), 2),
                        "volume_24h": f"${round(float(data['quoteVolume']) / 1000000, 2)}M" # 转换为百万美元(M)显示
                    }
                    logger.info(f"📈 成功获取 {token} 真实盘面: \
                                价格 ${market_info[token]['current_price']},\
                                  涨幅 {market_info[token]['24h_change_percent']}%")
                else:
                    logger.warning(f"⚠️ Binance 未找到 {symbol} 的交易对数据 (可能是非标代币或未上币安)。")
                    market_info[token] = {"error": "未收录该代币"}
            except Exception as e:
                logger.error(f"❌ 获取 {token} 市场数据时发生网络异常: {e}")
                market_info[token] = {"error": "数据抓取失败"}
            #防止并发过高被币安 API 封禁 IP
            await asyncio.sleep(0.5)
    logger.info(f">>> 市场数据获取成功: {market_info}")
    
    # 将字典返回，LangGraph 会自动更新到 AnalysisState 的 market_data 字段中
    return {"market_data": market_info}
async def final_decision_node(state: AnalysisState) -> dict:
    """
    节点 4：汇总所有信息，生成最终投资建议
    """
    logger.info(f"--- 节点 4：开始综合投资决策 | ID: {state['news_id']} ---")
    
    # 格式化输入数据，防止大模型理解错乱
    tokens_str = ", ".join(state.get("extracted_tokens", [])) or "无"
    market_data_str = json.dumps(state.get("market_data", {}), ensure_ascii=False)

    try:
        # 真正的大满贯调用：把所有上下文一并送入
        result: FinalDecisionOutput = await decision_chain.ainvoke({
            "news_content": state["news_content"],
            "extracted_tokens": tokens_str,
            "market_data": market_data_str,
            "retrieved_knowledge": state.get("retrieved_knowledge", "无可用背景知识") 
        })
        
        logger.info(f">>> 最终决策出炉: 动作=[{result.investment_action}], 理由数={len(result.reasons)}")
        
        return {
            "final_action": result.investment_action,
            "final_reasoning": result.reasons
        }
    except Exception as e:
        logger.error(f"决策节点发生异常: {e}")
        return {
            "final_action": "ignore",
            "final_reasoning": [f"AI 决策流水线崩溃，执行熔断保护。错误: {str(e)}"]
        }