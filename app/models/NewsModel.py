from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String,Text,DateTime,Boolean, JSON
from datetime import datetime, timezone
from app.db.base import Base
from sqlalchemy.sql import func

class NewsModel(Base):
    __tablename__ = "odaily_news"

    id: Mapped[int] = mapped_column(Integer,primary_key=True, comment="快讯唯一ID")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="快讯标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="快讯正文(已清洗)")
    publish_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        comment="快讯发布时间"
    )

    # 💡 额外提醒：created_at 的正确写法
    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), 
    nullable=False, 
    # 使用 server_default，SQLAlchemy 会在建表时加上 DEFAULT CURRENT_TIMESTAMP
    server_default=func.now(), 
    comment="记录入库时间")

    # --- AI 分析结果字段 (入库时为空，分析完后更新，所以 nullable=True) ---
    is_valuable: Mapped[bool] = mapped_column(Boolean, nullable=True, comment="是否有投资价值")
    sentiment: Mapped[str] = mapped_column(String(20), nullable=True, comment="情绪倾向(positive/neutral/negative)")
    # PostgreSQL 对 JSON 支持极好，用 JSON 存列表最合适
    extracted_tokens: Mapped[list] = mapped_column(JSON, nullable=True, comment="提取的代币列表")
    final_action: Mapped[str] = mapped_column(String(20), nullable=True, comment="最终投资建议(buy/sell/hold/ignore)")
    final_reasoning: Mapped[list] = mapped_column(JSON, nullable=True, comment="决策理由列表")

