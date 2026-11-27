import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, URL
from sqlalchemy.pool import NullPool
from sqlalchemy import text

load_dotenv()

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "6543")),
    database=os.getenv("DB_NAME", "postgres"),
    query={"sslmode": "require"}
)

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool
)



# def test_connection():
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(text("SELECT version()"))
#             print("Connected successfully!")
#             print(result.scalar())
#
#     except Exception as e:
#         print("Database connection failed:")
#         print(e)
#
#
# if __name__ == "__main__":
#     test_connection()
