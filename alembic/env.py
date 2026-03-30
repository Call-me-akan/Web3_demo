import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# ==========================================
# 1. 导入你的配置和所有模型
# ==========================================
from app.core.config import settings
# 【极其重要】：你必须在这里导入所有的 Model，否则 Alembic 就像个瞎子，看不到你的表结构！
from app.models.NewsModel import NewsModel
from app.models.Knowledge import KnowledgeModel

# 获取所有模型共用的 Base.metadata
# (假设你的 NewsModel 和 KnowledgeModel 都继承自同一个 Base)
target_metadata = NewsModel.metadata 

# ==========================================

config = context.config

# 读取 alembic.ini 中的日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 强制使用你在 settings 里定义的数据库连接，省去改 alembic.ini 的麻烦
# 确保你的 settings.DATABASE_URL 是 asyncpg 格式的
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    """异步执行迁移的核心逻辑"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        #run_sync妙用：由于 Alembic 的迁移内部逻辑是同步的，
        #所以需要通过connection.run_sync(do_run_migrations)这个“转换插头”，在异步环境里运行同步的迁移操作。
    await connectable.dispose()

def run_migrations_offline() -> None:
    """离线模式（极少使用）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """在线模式：通过 asyncio 运行"""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()