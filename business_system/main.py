"""
自动化业务分析系统 - 主入口
Automated Business Analysis System - Main Entry

启动方式:
    python main.py
    uvicorn main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

from config import (
    APP_HOST, APP_PORT, DATABASE_URL, DEBUG,
    ANTHROPIC_API_KEY, AI_MODEL, AI_MAX_TOKENS,
    UPLOAD_DIR, REPORTS_DIR,
    WECHAT_CORP_ID, WECHAT_CORP_SECRET, WECHAT_AGENT_ID, WECHAT_TOKEN,
    DINGTALK_ROBOT_WEBHOOK, DINGTALK_ROBOT_SECRET,
    EMAIL_IMAP_HOST, EMAIL_IMAP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD,
    EMAIL_CHECK_INTERVAL,
)
from database import init_db
from data_processing import DataProcessor, MarketAnalyzer, ReportGenerator
from ai import ConversationEngine
from api import router, init_services

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── 全局服务实例 ──────────────────────────────────────────────
processor = DataProcessor()
analyzer = MarketAnalyzer()
reporter = ReportGenerator(reports_dir=str(REPORTS_DIR))
conversation = ConversationEngine(
    api_key=ANTHROPIC_API_KEY,
    model=AI_MODEL,
    max_tokens=AI_MAX_TOKENS,
    analyzer=analyzer,
    reporter=reporter,
)

# ─── 邮件监听任务 ──────────────────────────────────────────────
_email_task = None


async def _start_email_polling():
    """启动邮件轮询（后台任务）"""
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        logger.info("邮件账号未配置，跳过邮件监听")
        return

    from integrations import EmailReceiver, DingTalkMessageHandler
    email_receiver = EmailReceiver(
        host=EMAIL_IMAP_HOST,
        port=EMAIL_IMAP_PORT,
        username=EMAIL_USERNAME,
        password=EMAIL_PASSWORD,
        upload_dir=str(UPLOAD_DIR),
    )

    async def on_email(msg):
        logger.info(f"收到邮件: {msg.get('subject')} from {msg.get('sender')}")
        for att in msg.get("attachments", []):
            filepath = att["filepath"]
            df = processor.process_file(filepath)
            if df is not None:
                analyzer.set_data(df)
                summary = processor.get_summary(df)
                logger.info(f"邮件附件数据已加载: {summary}")

    email_receiver.add_callback(on_email)
    await email_receiver.start_polling(interval=EMAIL_CHECK_INTERVAL)


# ─── 应用生命周期 ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    logger.info("🚀 系统启动中...")

    # 初始化数据库
    init_db(DATABASE_URL)
    logger.info("✅ 数据库初始化完成")

    # 确保目录存在
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 注入服务
    init_services(analyzer, reporter, conversation, processor)
    logger.info("✅ 服务注入完成")

    # 启动邮件轮询
    global _email_task
    _email_task = asyncio.create_task(_start_email_polling())

    logger.info(f"✅ 系统就绪 - http://{APP_HOST}:{APP_PORT}")

    yield  # 应用运行中

    # 关闭
    if _email_task:
        _email_task.cancel()
    logger.info("👋 系统已关闭")


# ─── FastAPI 应用 ──────────────────────────────────────────────

app = FastAPI(
    title="智能业务分析系统",
    description="""
## 自动化业务数据分析系统

### 核心功能
- **多通道数据接入**: 支持微信、钉钉、邮件自动接收数据
- **智能对话分析**: 自然语言查询，AI 驱动的分析洞察
- **市场分析**: 趋势、区域、产品、客户 RFM、渠道、KPI 等维度
- **报表生成**: HTML 交互式报表 / Excel 导出

### 接入方式
- 企业微信 Webhook: `POST /api/webhook/wechat`
- 钉钉机器人 Webhook: `POST /api/webhook/dingtalk`
- 邮件: IMAP 轮询 或 `POST /api/webhook/email`
- 文件上传: `POST /api/upload`
""",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(router, prefix="/api")

# 静态文件
static_dir = Path(__file__).parent / "ui" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 前端页面
template_path = Path(__file__).parent / "ui" / "templates" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """服务前端页面"""
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>UI 文件未找到</h1>")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ─── 入口 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info",
    )
