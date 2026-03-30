import json
import logging
import aio_pika
from aio_pika.abc import AbstractRobustConnection, AbstractChannel
#AbstractRobustConnection (连接)：这是物理层面的 TCP 连接。
#AbstractChannel (信道)：这是逻辑上的连接。
#理解：建立 TCP 连接很重。信道是在一个 TCP 连接里开辟的“虚拟通道”。你可以开几十个信道处理不同的业务（比如一个抓取，一个分析），而不需要开几十个 TCP 连接。
from app.core.config import settings
# from app.core.config import 
logger = logging.getLogger()

class RabbitMQClient:
    def __init__(self):
        self.connection: AbstractRobustConnection | None = None
        self.channel : AbstractChannel | None = None

        #定义队列名称
        self.queue_name = "web3_analysis_queue"
    
    async def connect(self):
        """简历稳定的异步连接并声明队列"""
        try:
            #connnect_robust会在网络抖动时重连
            self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()

            # 声明队列，durable=True 保证哪怕 RabbitMQ 容器重启，队列里的任务也不会丢
            await self.channel.declare_queue(self.queue_name, durable=True)
            logger.info("Rabbit连接成功，并持久化队列！")
        except Exception as e:
            logger.error(f"RabbitMQ连接失败：{e}")
        
    async def close(self):
        """所谓优雅关闭链接"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("RabbitMQ连接已关闭")

    async def publish_task(self, news_id:str):
        """生产者发送分析任务到队列"""
        if not self.channel:
            raise RuntimeError("RabbitMQ 尚未连接，无法发送消息！")

        message_body = json.dumps({"news_id": news_id}).encode()
        # delivery_mode=PERSISTENT 保证消息落盘，防止宕机丢失
        message = aio_pika.Message(
            body=message_body,
            delivery_mode=aio_pika.abc.DeliveryMode.PERSISTENT
        )
        await self.channel.default_exchange.publish(
            message,
            routing_key=self.queue_name
        )
        logger.debug(f"📤 分析任务已发送至队列: {news_id}")
# 导出一个全局单例供 FastAPI 路由使用
mq_client = RabbitMQClient()

            