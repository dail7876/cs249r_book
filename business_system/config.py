"""
自动化业务系统配置文件
Automated Business System Configuration
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ============================================================
# 数据库配置
# ============================================================
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/database/business.db")

# ============================================================
# 微信配置 (WeChat Work / 企业微信)
# ============================================================
WECHAT_CORP_ID = os.getenv("WECHAT_CORP_ID", "")
WECHAT_CORP_SECRET = os.getenv("WECHAT_CORP_SECRET", "")
WECHAT_AGENT_ID = os.getenv("WECHAT_AGENT_ID", "")
WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "your_wechat_token")
WECHAT_ENCODING_AES_KEY = os.getenv("WECHAT_ENCODING_AES_KEY", "")
WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL", "")

# ============================================================
# 钉钉配置 (DingTalk)
# ============================================================
DINGTALK_APP_KEY = os.getenv("DINGTALK_APP_KEY", "")
DINGTALK_APP_SECRET = os.getenv("DINGTALK_APP_SECRET", "")
DINGTALK_ROBOT_WEBHOOK = os.getenv("DINGTALK_ROBOT_WEBHOOK", "")
DINGTALK_ROBOT_SECRET = os.getenv("DINGTALK_ROBOT_SECRET", "")
DINGTALK_AGENT_ID = os.getenv("DINGTALK_AGENT_ID", "")

# ============================================================
# 邮件配置 (Email)
# ============================================================
EMAIL_IMAP_HOST = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
EMAIL_IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))
EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_CHECK_INTERVAL = int(os.getenv("EMAIL_CHECK_INTERVAL", "60"))  # seconds

# ============================================================
# AI 对话配置
# ============================================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-6")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4096"))

# ============================================================
# 应用配置
# ============================================================
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "change-this-secret-key-in-production")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# 文件上传
UPLOAD_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

# 支持的数据文件格式
SUPPORTED_FORMATS = [".xlsx", ".xls", ".csv", ".json"]

# ============================================================
# 市场分析配置
# ============================================================
MARKET_SEGMENTS = ["华东", "华北", "华南", "华中", "西南", "西北", "东北"]
PRODUCT_CATEGORIES = ["产品A", "产品B", "产品C", "产品D", "其他"]
SALES_CHANNELS = ["线上", "线下", "代理商", "直销", "电商平台"]
KPI_TARGETS = {
    "monthly_revenue": 1000000,
    "monthly_growth_rate": 0.15,
    "customer_acquisition": 500,
    "customer_retention_rate": 0.85,
}
