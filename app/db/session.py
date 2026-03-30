from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# 1. 创建异步引擎
#创建了一个连接池 (Connection Pool)
# echo=True 会打印所有 SQL 语句，方便你调试（生产环境要关掉）

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=False, 
    future=True
)

# 2. 创建 Session 工厂
# 以后我们在代码里操作数据库，都是通过这个 SessionLocal 领一个会话/批量生产
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# 3. 依赖注入函数 (Dependency)
# 这是 FastAPI 的核心模式：用 yield 确保每个请求用完 Session 后会自动关闭
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session