"""
自动化业务系统配置文件
Automated Business System Configuration
"""
import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # ── 应用基础配置 ──────────────────────────────────────────────────────────
    APP_NAME: str = "智能营销业务系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    SECRET_KEY: str = Field(default="change-this-in-production-secret-key", env="SECRET_KEY")

    # ── 数据库配置 ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/business.db",
        env="DATABASE_URL"
    )

    # ── Redis 缓存 ─────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # ── AI 对话配置 ────────────────────────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    AI_MODEL: str = Field(default="gpt-4o-mini", env="AI_MODEL")
    AI_BASE_URL: Optional[str] = Field(default=None, env="AI_BASE_URL")

    # ── 微信配置 ───────────────────────────────────────────────────────────────
    WECHAT_CORP_ID: Optional[str] = Field(default=None, env="WECHAT_CORP_ID")
    WECHAT_CORP_SECRET: Optional[str] = Field(default=None, env="WECHAT_CORP_SECRET")
    WECHAT_AGENT_ID: Optional[str] = Field(default=None, env="WECHAT_AGENT_ID")
    WECHAT_TOKEN: Optional[str] = Field(default=None, env="WECHAT_TOKEN")
    WECHAT_ENCODING_AES_KEY: Optional[str] = Field(default=None, env="WECHAT_ENCODING_AES_KEY")
    WECHAT_WEBHOOK_URL: Optional[str] = Field(default=None, env="WECHAT_WEBHOOK_URL")

    # ── 钉钉配置 ───────────────────────────────────────────────────────────────
    DINGTALK_APP_KEY: Optional[str] = Field(default=None, env="DINGTALK_APP_KEY")
    DINGTALK_APP_SECRET: Optional[str] = Field(default=None, env="DINGTALK_APP_SECRET")
    DINGTALK_ROBOT_WEBHOOK: Optional[str] = Field(default=None, env="DINGTALK_ROBOT_WEBHOOK")
    DINGTALK_ROBOT_SECRET: Optional[str] = Field(default=None, env="DINGTALK_ROBOT_SECRET")
    DINGTALK_CORP_ID: Optional[str] = Field(default=None, env="DINGTALK_CORP_ID")

    # ── 邮件配置 ───────────────────────────────────────────────────────────────
    EMAIL_IMAP_HOST: str = Field(default="imap.gmail.com", env="EMAIL_IMAP_HOST")
    EMAIL_IMAP_PORT: int = Field(default=993, env="EMAIL_IMAP_PORT")
    EMAIL_SMTP_HOST: str = Field(default="smtp.gmail.com", env="EMAIL_SMTP_HOST")
    EMAIL_SMTP_PORT: int = Field(default=587, env="EMAIL_SMTP_PORT")
    EMAIL_USER: Optional[str] = Field(default=None, env="EMAIL_USER")
    EMAIL_PASSWORD: Optional[str] = Field(default=None, env="EMAIL_PASSWORD")
    EMAIL_CHECK_INTERVAL: int = Field(default=300, env="EMAIL_CHECK_INTERVAL")  # 秒

    # ── 文件存储 ───────────────────────────────────────────────────────────────
    DATA_DIR: str = Field(default="./data", env="DATA_DIR")
    UPLOAD_DIR: str = Field(default="./data/uploads", env="UPLOAD_DIR")
    REPORT_DIR: str = Field(default="./data/reports", env="REPORT_DIR")
    MAX_UPLOAD_SIZE: int = Field(default=100 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 100MB

    # ── 报表配置 ───────────────────────────────────────────────────────────────
    REPORT_LOGO_PATH: Optional[str] = Field(default=None, env="REPORT_LOGO_PATH")
    COMPANY_NAME: str = Field(default="公司名称", env="COMPANY_NAME")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
