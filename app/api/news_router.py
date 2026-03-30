from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel,Field
from app.core.rabbitmq import mq_client
from app.db.session import get_db
from app.models.NewsModel import NewsModel
import logging
from typing import Optional, List
router = APIRouter()
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s' )
logger = logging.getLogger(__name__)
#---请求体规约---
class AnalyzeRequest(BaseModel):
    news_id: int = Field(...,description="快讯唯一ID")
    content: str = Field(...,description="快讯正文")

class AnalyzeResponse(BaseModel):
    message: str
    news_id: int

class AIAnalysisReport(BaseModel):
    news_id: int = Field(..., description="快讯唯一ID")
    title: str = Field(..., description="快讯标题")
    content: str = Field(..., description="快讯正文")
    status: str = Field(..., description="处理状态：pending(排队/分析中) | completed(已完成)")
    
    # AI 分析字段（排队时可能为空，所以用 Optional）
    is_valuable: Optional[bool] = Field(None, description="是否有投资价值")
    sentiment: Optional[str] = Field(None, description="情绪面: positive/neutral/negative")
    extracted_tokens: Optional[List[str]] = Field(default_factory=list, description="涉及的代币")
    final_action: Optional[str] = Field(None, description="投资动作: buy/sell/hold/ignore")
    final_reasoning: Optional[List[str]] = Field(default_factory=list, description="AI 决策逻辑推演")
    created_at: str = Field(..., description="入库时间")


@router.post("/analyze",response_model=AnalyzeResponse,summary="提交快讯分析任务")
async def submit_analysis_task(request:AnalyzeRequest):
    """
    接收前端发来的快讯，将其推入消息队列。
    """
    try:
        # 这里直接调用咱们封装好的 publish_task
        await mq_client.publish_task(request.news_id)
        logger.info(f"📦 [API 接收任务] 快讯 {request.news_id} 已成功送入 RabbitMQ 排队！")
        
        return {
            "message": "任务已接收，已进入 AI 分析队列排队中...", 
            "news_id": request.news_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任务提交失败: {str(e)}")
    
@router.get("/{news_id}",response_model=AIAnalysisReport,summary="查询分析结果")
async def get_analysis_result(news_id:int,db:AsyncSession = Depends(get_db)):
    """
    根据快讯 ID，去 PostgreSQL 数据库中查询最终的投资建议。
    """
    stmt = select(NewsModel).where(NewsModel.id == news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()

    if not news:
        raise HTTPException(status_code=404, detail="分析结果为查询到或仍在排队处理")
    if news.is_valuable is not None:
        task_status = "completed"

    return {
        "news_id": news.id,
        "title": news.title,
        "content": news.content,
        "status": task_status,
        "is_valuable": news.is_valuable,
        "sentiment": news.sentiment,
        # 兜底防御：如果是 None，强制转为空列表，防止前端报错
        "extracted_tokens": news.extracted_tokens or [],
        "final_action": news.final_action,
        "final_reasoning": news.final_reasoning or [],
        "created_at": news.created_at.strftime("%Y-%m-%d %H:%M:%S") if news.created_at else "未知"
        # 未来这里会加上: "action": news.final_action, "reasoning": news.final_reasoning
    }
    # Jiahui，这是你的第二个 TODO！
    # 既然你已经写过 CRUD，请在这里完成查询逻辑：
    # 1. 使用 SQLAlchemy 2.0 的 select 语法： select(NewsModel).where(NewsModel.id == news_id)
    # 2. 执行查询： await db.execute(...) 
    # 3. 提取结果： result.scalar_one_or_none()
    # 4. 如果没查到，抛出 HTTPException(status_code=404)
    # 5. 如果查到了，返回数据库里的记录。
