from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage,HumanMessage
from app.core.config import settings
import os
from httpx import AsyncClient
class LLMService:
    def __init__(self):
        #初始化大模型驱动
        #temperature = 0.1 ,模型更稳定减少胡言乱语
        
        os.environ["LANGSMITH_TRACING"] = settings.LANGSMITH_TRACING
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT    


        self.llm = ChatOpenAI(
            model_name = settings.LLM_MODEL_NAME,
            openai_api_key = settings.OPENAI_API_KEY,
            openai_api_base = settings.OPENAI_API_BASE,
            temperature = 0.1
        )
    async def get_response(self,prompt:str, system_prompt:str = "你是一个专业的AI助手" ):
        """最基础的异步对话方法"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        # 注意：我们这里用 ainvoke，保持全链路异步
        response = await self.llm.ainvoke(messages)
        return response.content
async def get_embdding(text:str)->list[float]:
        """调用硅基流动 API 获取异步向量"""
        url = "https://api.siliconflow.cn/v1/embeddings"
        playload = {
            "model":settings.EMBEDDING_MODEL,
            "input":text
        }
        headers = {
            "Authorization":f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
            }
        async with AsyncClient() as client:
            response =  await client.post(url, json = playload, headers = headers,timeout = 30.0)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
llm_service = LLMService()