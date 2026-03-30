import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime 
from app.services.crawler import OdailyCrawler  # 确保这里的路径对应你自己的爬虫类
from app.core.rabbitmq import mq_client
from app.core.config import settings
# logging.basicConfig(level=)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def scheduled_crawl_task():
    """这是每 5 分钟会被触发一次的核心任务"""
    logger.info("⏰ [定时任务触发] 开始执行自动化快讯抓取...")
    crawler = OdailyCrawler(redis_url = settings.REDIS_URL)

    try:
        # 1. 爬虫获取新快讯，并执行保存数据库操作
        # (前提：你的 process_pipeline 会返回刚才入库的 new_articles 列表)
        new_articles = await crawler.process_pipeline()

        if new_articles:
            for article in new_articles:
                # 注意：如果你的 article 是字典，用 article["news_id"]；如果是 Pydantic 对象，用 article.news_id
                news_id = article.news_id if hasattr(article, 'news_id') else article.get("news_id")
                await mq_client.publish_task(news_id)
                logger.info(f"🚀 调度器已自动将 {len(new_articles)} 条新快讯送入 AI 分析队列！")
        else:
            logger.info("📭 本次轮询未发现新快讯。")
        
    except Exception as e:
        logger.error(f"❌ 定时抓取任务发生致命异常: {e}")

def start_scheduler():
    """启动器调度的入口规则"""
    # 设定调度规则：每 5 分钟执行一次
    # 为了测试方便，你可以暂时把 minutes=5 改成 seconds=30，测试跑通后再改回来
    scheduler.add_job(scheduled_crawl_task,'interval',minutes=10,start_date=datetime.datetime.now())
    scheduler.start()
    logger.info("⏱️ APScheduler 定时调度器已成功挂载 (周期: 30s)")