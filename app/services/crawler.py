import asyncio
import httpx
import redis.asyncio as redis
import logging
from app.schema.OdailyNews import OdailyNewsItem
from app.core.config import settings
from app.db.session import AsyncSessionLocal, get_db
from fastapi import Depends
from app.models.NewsModel import NewsModel
from sqlalchemy import select
#配置log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s' )
logger = logging.getLogger(__name__)

class OdailyCrawler:
    def __init__(self, redis_url:str):
        #1.初始化Redis异步链接池，decode_responses=True表示将Redis中的字节数据byte自动解码为字符串str，方便后续处理
        self.redis = redis.from_url(redis_url,decode_responses=True)
        #2.初始化全局异步HTTP客户端（复用TCP连接池，设置超时时间）
        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        #有开就有关，关闭HTTP客户端和Redis连接池，释放资源
        await self.redis.close()
        await self.http_client.aclose()

    async def clean_id(self):
        """
        清理 Redis 中存在于缓存但 PostgreSQL 中已不存在的新闻 ID 对应的键。
        :param db_session: 异步数据库会话
        """
        logger.info("从pgsql拉取id")
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(NewsModel.id))
            existing_ids = set(str(id) for id, in result.fetchall())

        logger.info("从redis拉取id")
        redis_keys = await self.redis.keys("web3:news:odaily:*")
        for key in redis_keys:
            news_id = key.split(":")[-1]
            if news_id not in existing_ids:
                logger.info(f"清理过期快讯ID: {news_id}")
                await self.redis.delete(key)




    async def is_new_article(self, news_id:str) ->bool:
        """核心防刷逻辑：使用Redis的SETNX特性"""
        redis_key = f"web3:news:odaily:{news_id}"
        # Jiahui，这里是你的第一个 TODO！
        # 请使用 await self.redis.set(...) 方法。
        # 提示：你需要传入三个核心参数：
        # 1. key (也就是上面的 redis_key)
        # 2. value (随便存个值，比如 "1")
        # 3. nx=True (只有键不存在时才设置成功，这就是原子的“去重”动作)
        # 4. ex=86400 (设置 24 小时过期，防止内存爆炸)
        # 
        # 方法返回 True 表示这是新数据（拦截放行），返回 None/False 表示已存在（拦截丢弃）。
        result = await self.redis.set(redis_key, "1", nx=True, ex=86400)
        # result = await self.redis.set(...) 
        # return bool(result)
        return bool(result)
    async def fetch_latest_news(self) -> list[dict]:
        """异步获取快讯列表"""

        url = "https://web-api.odaily.news/newsflash/page?page=1&size=16&groupId=0&isImport=false"
        try:
            response = await self.http_client.get(url)
            logger.info(f"请求{url},状态码：{response.status_code}")
            # print(response.text)
            if response.status_code != 200:
                logger.error(f"请求失败，状态码：{response.status_code}")
                return []
            data = response.json()

            news_list =data['data']['list']
            # Jiahui，这是你的第二个 TODO！
            # 1. 使用 await self.http_client.get(url) 发起异步请求
            # 2. 检查状态码是否为 200 (response.raise_for_status())
            # 3. 解析 response.json()，提取出列表数据并 return
            return news_list
        except Exception as e:
            logger.error(f"抓取失败，可能是网络波动: {e}")
        # return list
    
    async def process_pipeline(self):
        #后需容量大了可以试用scan配合cursor来分批清理，避免一次性拉取过多数据导致内存问题
        # await self.clean_id()

        """流水线主逻辑：抓取、去重、打印"""
        logger.info("开始抓取快讯……")
        raw_news_list = await self.fetch_latest_news()

        new_articles = []
        for news in raw_news_list:
            # 假设 API 返回的数据里，快讯的唯一 ID 字段叫 'id'
            news_id = str(news.get("id"))

            #门卫Redis开始工作，去重
            if await self.is_new_article(news_id):
                logger.info(f"发现新快讯:{news_id}: {news.get('title')}")
                # new_articles.append(news)
                try:
                    #让原始字典数据通过 Pydantic 模型进行验证和清洗，变成结构化对象
                    clean_item = OdailyNewsItem(**news)
                    new_articles.append(clean_item)
                except Exception as e:
                    logger.error(f"数据验证失败，可能是字段缺失或格式错误: {e}")  
            else:
                logger.info(f"快讯已存在，跳过: {news_id}")
        
        await save_news_to_db(new_articles)

        return new_articles

async def main():
    crawler = OdailyCrawler(redis_url = settings.REDIS_URL)
    try:
        new_data = await crawler.process_pipeline()
        logger.info(f"本次共发现 {len(new_data)} 条新快讯")
    finally: await crawler.close()

async def save_news_to_db(news_items:list[OdailyNewsItem]):
    if not news_items:
        logger.info("没有新快讯需要保存到数据库")
        return
    async with AsyncSessionLocal() as db:
        try:
            #Pydantic(schemas)->SQlALchemy(models) -> 数据库
            db_models = [
                NewsModel(
                    id=item.news_id,
                    title=item.title,
                    content=item.content,
                    publish_at=item.publish_at
                )
                for item in news_items
            ]
            db.add_all(db_models)

            await db.commit()
            logger.info(f"成功保存 {len(db_models)} 条快讯到数据库")
        except Exception as e:
            await db.rollback()
            logger.error(f"数据库批量入库失败，已回滚！错误详情: {e}")
            # 视业务要求，这里可以选择抛出异常 raise e，或者静默处理。爬虫一般选择记录日志并继续
            raise RuntimeError("Database insertion failed") from e


if __name__ == "__main__":
    asyncio.run(main())
    