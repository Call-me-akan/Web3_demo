from typing import TypedDict, List, Literal, Optional
from pydantic import BaseModel, Field

#1.定义大模型的结构化输出模型

class ValueJudgmentOutput(BaseModel):
    """节点 1：投资价值判断的输出规约"""
    is_valuable: bool = Field(..., description="是否具有投资价值")
    sentiment: Literal["positive", "neutral", "negative"] = Field(..., description="快讯的情绪倾向")
    confidence_score: float = Field(..., ge=0, le=1, description="模型对判断的置信度评分，范围 0-1")
    reason: str = Field(..., description="模型判断的理由解释")


class TokenExtractionOutput(BaseModel):
    """节点 2：核心要素抽取的输出规约"""
    thinking_process: str = Field(
        ..., 
        description="一步步思考：1.文中有哪些实体？2.它们是传统机构/投资方/数据平台，还是有币的Web3项目？3.如果是后者，它在币安的现货交易对标准代码是什么（大写字母）？4.如果不确定或不是代币，必须排除。"
    )
    # 最终结果只能是纯纯的代币列表
    tokens: List[str] = Field(
        ..., 
        description="最终提取的标准代币代码列表，必须是连续的大写英文字母（如 BTC, SOL, DOGE）。严禁包含中文、空格或机构全称。如果没有，返回空列表 []。"
    )
    project_name: str = Field(..., description="涉及的项目名称")
    # event_type: str = Field(..., description="事件类型，如融资、合作、监管等")
    # event_time: str = Field(..., description="事件发生的时间，格式为 ISO 8601")
    # involved_parties: List[str] = Field(default_factory=list, description="涉及的主要参与方列表")

class FinalDecisionOutput(BaseModel):
    """节点 3：综合决策的输出规约"""
    investment_action: Literal["buy", "hold", "sell"] = Field(..., description="投资建议动作")
    reasons: List[str] = Field(default_factory=list, description="判断依据的理由列表")

#2定义langgraph的全局状态(TypedDict)
class AnalysisState(TypedDict):
    """
    这是贯穿整个图的状态。
    每个节点运行完毕后，都会返回一个字典来更新这里的对应字段。
    理解点：StateGraph会确保这个字典在节点之间流转。
    每个节点返回的字典，会自动根据你定义的**“合并规则（Reducers）”**更新到全局状态里。

    """
    #--初始输入--
    news_id:str
    news_content:str

# --- 节点 1 产生的结果 (价值判断) ---
    is_valuable: Optional[bool]
    sentiment: Optional[str]
    judgment_reason: Optional[str]

# --- 节点 2 产生的结果 (要素提取) ---
    project_name: Optional[str]
    # event_type: Optional[str]
    extracted_tokens: Optional[List[str]]

# --- 新增：节点 2.5 产生的结果 (检索到的背景知识) ---
    retrieved_knowledge: Optional[str]


# --- 节点 3 产生的结果 (Mock 市场数据，由外部函数补充，非大模型生成) ---
    market_data: Optional[dict]

# --- 节点 4 产生的结果 (最终决策) ---
    final_action: Optional[str]
    final_reasoning: Optional[List[str]]   