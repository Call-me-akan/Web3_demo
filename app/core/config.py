from pydantic_settings import BaseSettings,SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn,AmqpDsn,computed_field
from typing import Optional

#理解不够深刻

class Settings(BaseSettings):
    PROJECT_NAME: str = "Web3-investment-Analyzer"
    API_V1_STR: str = "/api/v1"

    # 数据库配置
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int = 5432

    # --- MinIO 配置 ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET_NAME: str = "nexus-knowledge-docs"

    # --- LLM 密钥 ---
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = ""
    LLM_MODEL_NAME: str = ""

    LANGSMITH_TRACING: Optional[str] = None
    LANGSMITH_ENDPOINT: Optional[str] = None
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: Optional[str] = None

    # --- Redis 配置 ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    REDIS_PASSWORD: Optional[str] = None

    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_USER: str = ""
    RABBITMQ_PASSWORD: str = ""
    RABBITMQ_PORT: int = None
    RABBITMQ_VHOST: str = ""
    EMBEDDING_DIMENSION: int = None


    EMBEDDING_MODEL : str  = ""

    @computed_field
    @property
    def RABBITMQ_URL(self) -> str:
        """自动拼接生成 RabbitMQ 连接字符串：amqp://user:password@host:port/vhost"""
        return str(AmqpDsn.build(
        scheme="amqp",  # RabbitMQ 使用的 AMQP 协议
        username=self.RABBITMQ_USER,
        password=self.RABBITMQ_PASSWORD,
        host=self.RABBITMQ_HOST,
        port=self.RABBITMQ_PORT,
        # RabbitMQ 的 path 代表 Virtual Host (vhost)
        # 注意：如果 vhost 是默认的 "/"，通常在 URL 中表示为 "//"
        path=f"{self.RABBITMQ_VHOST}" if self.RABBITMQ_VHOST else "/",
    ))


    @computed_field
    @property
    def REDIS_URL(self) ->str:
        """自动拼接生成 Redis 连接字符串：redis://:password@host:port/db"""
        # if self.REDIS_PASSWORD:
        #     return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}/0"
        # else:
        #     return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}/0"
        return str(RedisDsn.build(
            scheme="redis",
            username="",  # Redis URL 中通常不使用用户名
            password=self.REDIS_PASSWORD,
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            path=f"/{self.REDIS_DB}",
        ))  



        

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """
        自动拼接生成数据库连接字符串：
        postgresql+asyncpg://user:pass@host:port/db
        """
        return str(PostgresDsn.build(
            scheme="postgresql+asyncpg",  # 重点：使用异步驱动
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        ))
    @property
    def DATABASE_URL(self) -> str:
        """为 Alembic 等外部工具提供的数据库 URL 别名"""
        return self.SQLALCHEMY_DATABASE_URI
    #Pydantic V2 的标准规范中，更推荐且更稳定的做法是使用 SettingsConfigDict
    model_config = SettingsConfigDict(
        env_file= ".env",
        extra="ignore"  # 忽略 .env 里多余的字段（比如 REDIS 配置先不管）
    )
    


# input_data = {
#     "PROJECT_NAME" : "Nexus-RAG-Agent",
#     "API_V1_STR" : "/api/v1",

#     # 数据库配置
#     "POSTGRES_SERVER": "test",
#     "POSTGRES_USER": "admin",
#     "POSTGRES_PASSWORD": "123456",
#     "POSTGRES_DB": "defalut",
#     "POSTGRES_PORT":5432,
# }

settings = Settings()
# print(settings.SQLALCHEMY_DATABASE_URI)
print(settings.RABBITMQ_URL)

