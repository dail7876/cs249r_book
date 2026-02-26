"""
数据库模型与持久化层
Database Models and Persistence Layer (SQLite via SQLAlchemy async)
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text,
    Boolean, ForeignKey, JSON, create_engine
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.future import select
from loguru import logger

from config import settings

Base = declarative_base()

# ── ORM 模型 ───────────────────────────────────────────────────────────────────

class SalesRecord(Base):
    """营销销售记录表"""
    __tablename__ = "sales_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, index=True)
    product = Column(String(200), index=True)
    category = Column(String(100), index=True)
    region = Column(String(100), index=True)
    channel = Column(String(100), index=True)
    customer = Column(String(200), index=True)
    salesperson = Column(String(100))
    quantity = Column(Float, default=0)
    sales = Column(Float, default=0)
    cost = Column(Float, default=0)
    profit = Column(Float, default=0)
    profit_rate = Column(Float, default=0)
    order_id = Column(String(100))
    status = Column(String(50))
    source_file = Column(String(500))
    source = Column(String(50), default="manual")  # manual/wechat/dingtalk/email
    extra = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class DataUpload(Base):
    """数据上传记录"""
    __tablename__ = "data_uploads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500))
    file_path = Column(String(1000))
    file_size = Column(Integer)
    source = Column(String(50))  # wechat/dingtalk/email/web
    rows_imported = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending/processing/done/failed
    error_msg = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)


class ChatSession(Base):
    """AI 对话会话"""
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, index=True)
    user_id = Column(String(100))
    channel = Column(String(50), default="web")  # web/wechat/dingtalk
    started_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    """对话消息记录"""
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("chat_sessions.session_id"), index=True)
    role = Column(String(20))  # user/assistant/system
    content = Column(Text)
    tool_calls = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    session = relationship("ChatSession", back_populates="messages")


class Report(Base):
    """生成的报表记录"""
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500))
    report_type = Column(String(100))  # daily/weekly/monthly/custom/analysis
    file_path = Column(String(1000))
    parameters = Column(JSON)
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String(100))


# ── 引擎 & Session 工厂 ────────────────────────────────────────────────────────
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """初始化数据库（创建所有表）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库初始化完成")


async def get_db():
    """FastAPI 依赖注入：获取 DB Session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ── CRUD 帮助函数 ──────────────────────────────────────────────────────────────
async def bulk_insert_sales(records: List[Dict[str, Any]], source_file: str,
                             source: str = "web") -> int:
    """批量插入销售记录，返回插入行数"""
    rows = []
    for r in records:
        obj = SalesRecord(
            date=r.get("date"),
            product=r.get("product"),
            category=r.get("category"),
            region=r.get("region"),
            channel=r.get("channel"),
            customer=r.get("customer"),
            salesperson=r.get("salesperson"),
            quantity=r.get("quantity", 0) or 0,
            sales=r.get("sales", 0) or 0,
            cost=r.get("cost", 0) or 0,
            profit=r.get("profit", 0) or 0,
            profit_rate=r.get("profit_rate", 0) or 0,
            order_id=r.get("order_id"),
            status=r.get("status"),
            source_file=source_file,
            source=source,
            extra={k: v for k, v in r.items()
                   if k not in SalesRecord.__table__.columns.keys()}
        )
        rows.append(obj)
    async with AsyncSessionLocal() as session:
        session.add_all(rows)
        await session.commit()
    return len(rows)
