# from sqlalchemy.ext.asyncio import AsyncEngine
# from sqlalchemy.orm import sessionmaker
# from sqlmodel import SQLModel, create_engine
# from sqlmodel.ext.asyncio.session import AsyncSession

# from config import Config

# async_engine = AsyncEngine(create_engine(url=Config.DATABASE_URL))


# async def init_db() -> None:
#     async with async_engine.begin() as conn:
#         await conn.run_sync(SQLModel.metadata.create_all)


# async def get_session() -> AsyncSession:
#     Session = sessionmaker(
#         bind=async_engine, class_=AsyncSession, expire_on_commit=False
#     )

#     async with Session() as session:
#         yield session


from typing import Annotated
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

""" You can add a DATABASE_URL environment variable to your .env file """
# DATABASE_URL = os.getenv("DATABASE_URL")

""" Or hard code SQLite here """
# DATABASE_URL = "sqlite:///./todosapp.db"

""" Or hard code PostgreSQL here """
DATABASE_URL = "mssql+pyodbc://sa:sa%4012309876@192.168.152.22:1433/SONA-MESX0-QA-TEST-SAP?driver=ODBC+Driver+17+for+SQL+Server"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
DbSession = Annotated[Session, Depends(get_db)]