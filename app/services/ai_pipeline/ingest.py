import asyncio
from httpx import AsyncClient
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.Knowledge import KnowledgeModel

logging.basicConfig(level= logging.INFO)
logger = logging.getLogger(__name__)

SILICONFLOW_API_KEY = settings.OPENAI_API_KEY
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"


async def get_embdding(text:str)->list[float]:
    """调用硅基流动 API 获取异步向量"""
    url = "https://api.siliconflow.cn/v1/embeddings"
    playload = {
        "model":EMBEDDING_MODEL,
        "input":text
    }
    headers = {
        "Authorization":f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
        }
    async with AsyncClient() as client:
        response =  await client.post(url, json = playload, headers = headers,timeout = 30.0)
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

async def ingest_document(project_name: str, raw_text: str):
    """文档切片并入库"""
    logger.info(f"开始处理项目 [{project_name}] 的文档...")
    # 1. 文本切片 (Chunking)
    # 将长篇大论切成一小块一小块，方便大模型精准检索
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,  # 每块大约 500 字
        chunk_overlap=50 # 块与块之间重叠 50 字，防止把一句话从中间切断
    )
    chunks = text_splitter.split_text(raw_text)
    logger.info(f"文档已切分为 {len(chunks)} 个片段，开始获取向量...")

    async with AsyncSessionLocal() as db:
        for i , chunk_text in enumerate(chunks):
            try:
                vector = await get_embdding(chunk_text)

                doc = KnowledgeModel(
                    project_name = project_name,
                    content = chunk_text,
                    embedding = vector,
                    metadata_info = {"chunk_index": i,"source":"whitepaper"}
                )
                db.add(doc)
                logger.info(f"✅ 成功处理第 {i+1}/{len(chunks)} 块切片")
            except Exception as e:
                logger.error(f"❌ 处理第 {i+1} 块切片时出错: {e}")
                raise e
        try:        
            await db.commit()
            logger.info(f"🎉 项目 [{project_name}] 的所有背景知识已成功灌入 pgvector 知识库！")
        except Exception as e:
            await db.rollback() # 显式回滚，释放锁
            logger.error(f"❌ 批量入库提交失败，已执行回滚: {e}")
async def main():
    # 模拟一篇 Solana 的长篇研报或技术白皮书片段
    mock_solana_whitepaper = """
    Solana 是一个高性能的底层区块链平台，旨在提供去中心化、可扩展和安全的应用程序环境。
    其核心创新之一是历史证明（Proof of History, PoH）。PoH 并不是一种共识机制，而是一种加密时钟，
    它可以证明某个消息在特定的时间发生过。结合实用拜占庭容错（PBFT）的变体 Tower BFT，
    Solana 能够实现极高的吞吐量（TPS 可达 65,000）和极低的交易延迟。
    近期，Solana 基金会宣布了一项关于节点优化的重要升级，预计将进一步降低网络的 Gas 费用，
    这引起了机构投资者的高度关注。
    """
    
    await ingest_document(project_name="Solana", raw_text=mock_solana_whitepaper)

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())