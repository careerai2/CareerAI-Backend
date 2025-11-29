from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from config.env_config import DATABASE_URL

print(f"Connecting to Postgress database at {DATABASE_URL}")
engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

# Dependency for FastAPI
async def get_postgress_db():
    async with AsyncSessionLocal() as session:
        yield session
