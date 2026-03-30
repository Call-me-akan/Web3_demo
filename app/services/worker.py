import asyncio
import json
import logging
import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select,update

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.NewsModel import NewsModel
from app.services.ai_pipeline.graph import app as ai_graph

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def process_message(message: AbstractIncomingMessage):
    """
    处理单条消息的核心逻辑
    """
    # 开启 message.process() 上下文管理器，一旦代码成功跑完，它会自动向 RabbitMQ 发送 ACK
    # 如果中间抛出异常，它会自动发送 NACK，让消息重新入队
    async with message.process():
        body = json.loads(message.body.decode())
        news_id = body.get("news_id")

        logger.info(f"📥 [Worker 收到任务] 准备分析快讯: {news_id}")

        async with AsyncSessionLocal() as db:
            stmt = select(NewsModel).where(NewsModel.id == news_id)
            result = await db.execute(stmt)
            news = result.scalar_one_or_none()

            if not news:
                logger.error(f"❌ 数据库中未找到快讯 {news_id}，放弃处理。")
                return
            
            ai_input = {
                "news_id": news.id,
                "news_content": news.content
            }
            logger.info(f"🧠 [启动 AI 分析] 快讯 {news_id} 已送入 LangGraph 流水线...")

            try:
                final_state = await ai_graph.ainvoke(ai_input)
                #全局的最终快照，通常是Typedict，用get取值
                is_valuable = final_state.get("is_valuable", False)
                sentiment = final_state.get("sentiment", "neutral")
                extracted_tokens = final_state.get("extracted_tokens", [])
                final_action = final_state.get("final_action", "ignore")
                final_reasoning = final_state.get("final_reasoning", [])

                logger.info(f"✅ [AI 分析完成] {news_id} 结论: {final_action}")

                #更新回pgsql里
                updata_stmt = (update(NewsModel)
                               .where(NewsModel.id == news_id)
                               .values(
                                   is_valuable = is_valuable,
                                   sentiment = sentiment,
                                   extracted_tokens = extracted_tokens,
                                    final_action = final_action,
                                    final_reasoning = final_reasoning
                               ))
                await db.execute(updata_stmt)
                await db.commit()
                logger.info(f"💾 [数据落库] 快讯 {news_id} 分析结果已成功写入数据库！")
            except Exception as e:
                logger.error(f"❌ [分析或入库失败] 快讯 {news_id} 处理异常: {e}")
                await db.rollback()
                raise e
async def main():
    """
    Worker 启动主循环
    """
    logger.info("🚀 Web3 AI 分析 Worker 正在启动...")
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)

    async with connection:
        channel = await connection.channel()
        # prefetch_count=5 意味着这个 Worker 同时最多向 AI 引擎发起 5 个并发请求，保护大模型不被熔断
        await channel.set_qos(prefetch_count=5)
        queue = await channel.declare_queue("web3_analysis_queue", durable=True)


        logger.info("🎧 Worker 已经就绪，正在持续监听队列...")
        # 绑定消费回调函数 
        await queue.consume(process_message)
        # 挂起当前协程，让 Worker 永远运行下去
        await asyncio.Future()

if __name__ == "__main__":
    import sys
    if sys.platform =="win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())