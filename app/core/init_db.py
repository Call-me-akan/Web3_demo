import asyncio
import logging
from app.db.base import Base
from app.models.NewsModel import NewsModel
from app.schema.OdailyNews import OdailyNewsItem
from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_model():
    logger.info("正在连接数据库并创建表结构")

    async with engine.begin() as conn:
        logger.info("正在清理旧表结构...")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库初始化完成")


if __name__ =='__main__':
    asyncio.run(init_model())