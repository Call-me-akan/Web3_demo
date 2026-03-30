from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String,Text,DateTime,Boolean, JSON
from datetime import datetime, timezone
from app.db.base import Base
# from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.core.config import settings
class KnowledgeModel(Base):
    __tablename__ = "project_knowledge"

    id: Mapped[int] = mapped_column(Integer,primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String(100),index=True,comment="关联的项目名，用于硬过滤")
    content : Mapped[str ]= mapped_column(Text,nullable=False, comment="文档切片内容")
    # 核心：1536维度的向量字段（对应 OpenAI 的 text-embedding-3-small）
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIMENSION), comment="文档向量")
    
    # 存一些元数据，比如来源文件名、页码等
    metadata_info: Mapped[dict] = mapped_column(JSONB, nullable=True, comment="元数据")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)