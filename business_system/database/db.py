"""
数据库模型和操作
Database Models and Operations
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Text, Boolean, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum

Base = declarative_base()


class DataSource(enum.Enum):
    WECHAT = "wechat"
    DINGTALK = "dingtalk"
    EMAIL = "email"
    MANUAL = "manual"
    API = "api"
    UPLOAD = "upload"


class MessageStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


# ============================================================
# 数据模型
# ============================================================

class IncomingMessage(Base):
    """接收到的消息/数据"""
    __tablename__ = "incoming_messages"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(SAEnum(DataSource), nullable=False)
    sender = Column(String(200))
    content = Column(Text)
    raw_data = Column(JSON)
    status = Column(SAEnum(MessageStatus), default=MessageStatus.PENDING)
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class SalesRecord(Base):
    """销售记录"""
    __tablename__ = "sales_records"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    product_name = Column(String(200))
    category = Column(String(100))
    region = Column(String(100))
    sales_channel = Column(String(100))
    quantity = Column(Integer, default=0)
    unit_price = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    profit = Column(Float, default=0.0)
    profit_margin = Column(Float, default=0.0)
    customer_id = Column(String(100), nullable=True)
    customer_name = Column(String(200), nullable=True)
    salesperson = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)
    source = Column(SAEnum(DataSource), default=DataSource.MANUAL)
    created_at = Column(DateTime, default=datetime.utcnow)


class Customer(Base):
    """客户信息"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), unique=True, index=True)
    name = Column(String(200))
    company = Column(String(300), nullable=True)
    region = Column(String(100), nullable=True)
    segment = Column(String(100), nullable=True)
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    total_purchases = Column(Float, default=0.0)
    purchase_count = Column(Integer, default=0)
    first_purchase = Column(DateTime, nullable=True)
    last_purchase = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketIndicator(Base):
    """市场指标"""
    __tablename__ = "market_indicators"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    period_type = Column(String(20))  # daily, weekly, monthly
    region = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    total_revenue = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    total_profit = Column(Float, default=0.0)
    order_count = Column(Integer, default=0)
    customer_count = Column(Integer, default=0)
    new_customers = Column(Integer, default=0)
    avg_order_value = Column(Float, default=0.0)
    growth_rate = Column(Float, nullable=True)
    market_share = Column(Float, nullable=True)
    calculated_at = Column(DateTime, default=datetime.utcnow)


class ConversationSession(Base):
    """对话会话"""
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True)
    user_id = Column(String(100), nullable=True)
    source = Column(String(50), default="web")
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    context = Column(JSON, nullable=True)
    messages = relationship("ConversationMessage", back_populates="session")


class ConversationMessage(Base):
    """对话消息"""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id"))
    role = Column(String(20))  # user, assistant
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, nullable=True)
    session = relationship("ConversationSession", back_populates="messages")


class Report(Base):
    """生成的报表"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300))
    report_type = Column(String(100))
    parameters = Column(JSON, nullable=True)
    file_path = Column(String(500), nullable=True)
    format = Column(String(20), default="html")  # html, pdf, excel
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String(100), nullable=True)


# ============================================================
# 数据库连接和会话管理
# ============================================================

_engine = None
_SessionLocal = None


def get_engine(database_url: str):
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
        )
    return _engine


def init_db(database_url: str):
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    global _SessionLocal
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine


def get_session():
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
