
import os

from dotenv import load_dotenv
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "6543")),
    database=os.getenv("DB_NAME", "postgres"),
    query={"ssl": "require"}
)

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0
    }
)