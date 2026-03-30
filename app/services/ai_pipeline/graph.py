import asyncio
import logging
from langgraph.graph import StateGraph, START, END

# 导入我们的图状态和刚才写好的异步节点
from app.services.ai_pipeline.state import AnalysisState

from app.services.ai_pipeline.nodes import (
    analyze_value_node, 
    extract_token_node, 
    retrieve_knowledge_node,
    router_judgment, 
    fetch_market_data_node,
    final_decision_node  # <--- 新增导入
)
# 日志配置
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# 1. 初始化状态图 (StateGraph)
# ==========================================
# 把 AnalysisState 作为泛型传入，图就知道该用什么数据结构来当“传送带”了
workflow = StateGraph(AnalysisState)

# ==========================================
# 2. 注册节点 (Nodes)
# ==========================================
# 第一个参数是节点的唯一名称，第二个参数是对应的执行函数
workflow.add_node("value_judgment", analyze_value_node)
workflow.add_node("extract_token", extract_token_node)
workflow.add_node("retrieve_knowledge_node",retrieve_knowledge_node)
workflow.add_node("fetch_market_data", fetch_market_data_node)
workflow.add_node("final_decision", final_decision_node)


# ==========================================
# 3. 编排流转路径 (Edges)
# ==========================================
# 目前没有条件判断，直接走一条直线
workflow.add_edge(START, "value_judgment")
workflow.add_conditional_edges(
    "value_judgment",  # 离开哪个节点后触发路由
    router_judgment,    # 我们刚才写的路由逻辑函数
    {
        # 字典映射：路由函数返回的字符串 -> 图中真实的节点名
        "extract_token": "extract_token",
        END: END
    }
)
# 节点 2 (提取) 完成后，流转到节点 3 (获取数据)
workflow.add_edge("extract_token", "retrieve_knowledge_node")
#节点 2.5 知识库查询
workflow.add_edge("retrieve_knowledge_node","fetch_market_data")
# 节点 3 (获取数据) 完成后，进入节点 4 (最终决策)
workflow.add_edge("fetch_market_data", "final_decision")

# 节点 4 完成后，整个流水线才真正结束！
workflow.add_edge("final_decision", END)
# ==========================================
# 4. 编译成可执行应用 (Compile)
# ==========================================
app = workflow.compile()


# ==========================================
# MVP 测试沙盒 (直接运行当前脚本即可测试)
# ==========================================
async def main():
    logger.info("🚀 启动 LangGraph v2 (带条件路由) 本地测试...")
    
    # 我们可以准备两个用例来测试路由是否生效
    
    # 用例 A：有价值新闻（应该走完提取节点）
    mock_valuable = {
        "news_id": "test_001",
        "news_content": "重磅！Solana 基金会宣布与谷歌云达成深度战略合作，共同推出 1 亿美元的去中心化基础设施基金，SOL 价格短线拉升。"
    }
    
    # 用例 B：垃圾噪音新闻（应该在节点 1 之后直接 END）
    mock_garbage = {
        "news_id": "test_002",
        "news_content": "知名 KOL 'Crypto狗' 在推特表示，他今天早饭吃得很饱，感觉今天的大盘会涨。"
    }

    try:
        # logger.info("\n==========  📊测试用例 A==========")
        logger.info("\n========== 📊 测试用例 A: 完整生命周期输出 ==========")
        state_a = await app.ainvoke(mock_valuable)
        logger.info(f"【提取代币】: {state_a.get('extracted_tokens')}")
        logger.info(f"【市场数据】: {state_a.get('market_data')}")
        logger.info(f"【投资动作】: {state_a.get('final_action')}")
        logger.info(f"【决策理由】: {state_a.get('final_reasoning')}")
        logger.info("====================================================")
        # logger.info("\n========== 测试用例 B (应该被路由拦截) ==========")
        # state_b = await app.ainvoke(mock_garbage)
        # logger.info(f"用例 B 最终状态中的代币字段: {state_b.get('extracted_tokens')} (应该是 None)")
        
    except Exception as e:
        logger.error(f"❌ 图执行失败: {e}")
    
if __name__ == "__main__":
    # 保证在 Windows 环境下也能丝滑运行 asyncio
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())
    