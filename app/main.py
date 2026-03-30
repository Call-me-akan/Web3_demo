from fastapi import FastAPI
from app.core.config import settings
from app.api import news_router
from app.core.rabbitmq import mq_client  # 导入 mq_client
from contextlib import asynccontextmanager
from app.core.scheduler import start_scheduler, scheduler,scheduled_crawl_task
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 启动时执行 ---
    print("🚀 系统启动中：正在连接 RabbitMQ...")
    await mq_client.connect()
    await scheduled_crawl_task()
    start_scheduler()
    yield
    # --- 停止时执行 ---
    print("🛑 系统关闭中：正在断开 RabbitMQ...")
    scheduler.shutdown()
    await mq_client.close()

def create_app() ->FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        lifespan = lifespan,
        description="AI 驱动的 Web3 投资分析系统 API",
        version="1.0.0",
        docs_url="/docs") # 咱们调试的主力工具
    app.include_router(
        news_router.router,
        prefix="/api/v1/news",
        tags=["News Analysis"]
    )
    return app
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app",host="0.0.0.0",port=8000,reload=True)
