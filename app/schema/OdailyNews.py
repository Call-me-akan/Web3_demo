from pydantic import BaseModel, Field,field_validator
from datetime import datetime, timezone
import re
from typing import List, Optional
import html

HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

class OdailyNewsItem(BaseModel):
    # 使用 alias 可以完美解决外部 API 字段名（比如 id）与我们内部命名规范冲突的问题
    news_id: Optional[int] = Field(alias = "id",description="快讯唯一 标识")
    title: str = Field(...,description="快讯标题")
    content: str = Field(alias="description",description="快讯正文（可能包含 HTML 标签）")
    publish_at: datetime = Field(alias="publishTimestamp",description="快讯发布时间")

    @field_validator("publish_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v): 
        """
        时间转化器：如果是 Unix 时间戳格式（无论是整数还是字符串数字），自动转换为 datetime 对象。
        如果外部给的已经是标准时间格式的字符串（如 "2026-03-18T12:00:00"），Pydantic 底层会自动处理。
        """
        if isinstance(v, (int, float)):
            # 兼容 13 位毫秒级时间戳或 10 位秒级时间戳
            return datetime.fromtimestamp(v / 1000 if v > 1e10 else v,tz=timezone.utc)
        elif isinstance(v, str) and v.isdigit():
            v_int = int(v)
            return datetime.fromtimestamp(v_int / 1000 if v_int > 1e10 else v_int,tz=timezone.utc)
        return v
    @field_validator("content")#不需要before？因为把一个带HTML标签的字符串转成字符串，是不会报错的。你可以放心让Pydantic先完成它的“基础安检（类型确认）”，然后你再进行后续的“深度美容（数据清洗）”
    @classmethod
    def clean_html_tags(cls,v:str) -> str:
        # 使用正则表达式去除 HTML 标签
        if not v:
            return ""
        cleantext = HTML_TAG_PATTERN.sub('', v)
        cleantext = html.unescape(cleantext) # 将 HTML 实体转换回普通字符（比如把 &nbsp; 变成空格，&amp; 变成 &）
        return cleantext.strip()     

