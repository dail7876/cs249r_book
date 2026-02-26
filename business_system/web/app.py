"""
FastAPI 主应用
Main FastAPI Application

提供 REST API + WebSocket 实时对话接口
"""
import os
import json
import uuid
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import (
    FastAPI, File, UploadFile, HTTPException, Depends,
    WebSocket, WebSocketDisconnect, BackgroundTasks, Request
)
from fastapi.responses import (
    HTMLResponse, FileResponse, JSONResponse, StreamingResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from loguru import logger

# ── 系统路径配置 ───────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from modules.processing.database import init_db, bulk_insert_sales, DataUpload, AsyncSessionLocal
from modules.processing.excel_processor import ExcelProcessor
from modules.analysis.market_analysis import analyzer as market_analyzer
from modules.reporting.report_generator import ReportGenerator
from modules.chat.dialog_handler import dialog_handler
from modules.ingestion.wechat import wechat_receiver, WeChatMessage
from modules.ingestion.dingtalk import dingtalk_receiver, DingTalkMessage
from modules.ingestion.email_handler import email_receiver

# ── FastAPI 应用实例 ───────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="智能营销业务系统 API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 静态文件 & 模板 ─────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# ── WebSocket 连接管理 ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, session_id: str):
        await ws.accept()
        self.active[session_id] = ws

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send(self, session_id: str, message: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(message)

ws_manager = ConnectionManager()

# ── 全局报表生成器 ─────────────────────────────────────────────────────────────
report_gen = ReportGenerator(market_analyzer)

# ── 启动事件 ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.REPORT_DIR, exist_ok=True)
    await init_db()
    # 启动邮件轮询（后台任务）
    if settings.EMAIL_USER:
        asyncio.create_task(email_receiver.start_polling())
    logger.info(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} 已启动")


# ══════════════════════════════════════════════════════════════════════════════
# 前端页面路由
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request,
                                                       "app_name": settings.APP_NAME})


# ══════════════════════════════════════════════════════════════════════════════
# API: 数据上传与管理
# ══════════════════════════════════════════════════════════════════════════════

class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    rows: int
    columns: List[str]
    summary: dict


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    source: str = "web"
):
    """上传营销数据文件（Excel / CSV）"""
    allowed_ext = {".xlsx", ".xls", ".xlsm", ".csv"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_ext:
        raise HTTPException(400, f"不支持的文件格式: {suffix}，请上传 Excel 或 CSV 文件")

    upload_id = str(uuid.uuid4())
    save_path = os.path.join(settings.UPLOAD_DIR, f"{upload_id}_{file.filename}")

    # 保存文件
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(413, "文件太大，最大支持 100MB")
    with open(save_path, "wb") as f:
        f.write(content)
    logger.info(f"文件已上传: {save_path}")

    # 处理文件
    try:
        proc = ExcelProcessor()
        proc.load_file(save_path)
        clean_df = proc.clean()
        summary = proc.get_summary()

        # 更新全局分析器
        market_analyzer.set_data(clean_df)

        # 后台写入数据库
        records = clean_df.to_dict("records")
        background_tasks.add_task(bulk_insert_sales, records, save_path, source)

        return UploadResponse(
            upload_id=upload_id,
            filename=file.filename,
            rows=len(clean_df),
            columns=list(clean_df.columns),
            summary=summary
        )
    except Exception as e:
        logger.error(f"数据处理失败: {e}")
        raise HTTPException(500, f"数据处理失败: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# API: 市场分析
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/analysis/kpi")
async def api_kpi(date_from: Optional[str] = None, date_to: Optional[str] = None):
    try:
        return market_analyzer.overall_kpi(date_from, date_to)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/trend")
async def api_trend(freq: str = "ME",
                    date_from: Optional[str] = None,
                    date_to: Optional[str] = None):
    try:
        return market_analyzer.sales_trend(freq, date_from, date_to)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/multi-trend")
async def api_multi_trend(metrics: str = "sales,profit", freq: str = "ME"):
    try:
        m_list = [m.strip() for m in metrics.split(",")]
        return market_analyzer.multi_metric_trend(m_list, freq)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/products")
async def api_products(top_n: int = 10,
                        date_from: Optional[str] = None,
                        date_to: Optional[str] = None):
    try:
        return market_analyzer.product_analysis(top_n, date_from, date_to)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/regions")
async def api_regions(top_n: int = 10,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None):
    try:
        return market_analyzer.region_analysis(top_n, date_from, date_to)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/channels")
async def api_channels(date_from: Optional[str] = None, date_to: Optional[str] = None):
    try:
        return market_analyzer.channel_analysis(date_from, date_to)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/rfm")
async def api_rfm(reference_date: Optional[str] = None):
    try:
        return market_analyzer.rfm_analysis(reference_date)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/yoy-mom")
async def api_yoy_mom(target_period: Optional[str] = None):
    try:
        return market_analyzer.yoy_mom_comparison(target_period)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/forecast")
async def api_forecast(periods: int = 6, freq: str = "ME"):
    try:
        return market_analyzer.simple_forecast(periods, freq)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/anomalies")
async def api_anomalies(column: str = "sales", std_multiplier: float = 2.0):
    try:
        return market_analyzer.detect_anomalies(column, std_multiplier)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/analysis/category-region-matrix")
async def api_matrix():
    try:
        return market_analyzer.category_region_matrix()
    except Exception as e:
        raise HTTPException(400, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# API: 报表生成与下载
# ══════════════════════════════════════════════════════════════════════════════

class ReportRequest(BaseModel):
    format: str = "html"
    title: str = "营销数据分析报告"
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@app.post("/api/reports/generate")
async def generate_report(req: ReportRequest):
    try:
        if req.format == "excel":
            path = report_gen.generate_excel_report(req.title, req.date_from, req.date_to)
        else:
            path = report_gen.generate_html_report(req.title, req.date_from, req.date_to)
        filename = os.path.basename(path)
        return {
            "status": "success",
            "file_path": path,
            "filename": filename,
            "download_url": f"/api/reports/download/{filename}"
        }
    except Exception as e:
        raise HTTPException(500, f"报表生成失败: {str(e)}")


@app.get("/api/reports/download/{filename}")
async def download_report(filename: str):
    path = os.path.join(settings.REPORT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "文件不存在")
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if filename.endswith(".xlsx") else "text/html"
    )
    return FileResponse(path, filename=filename, media_type=media_type)


@app.get("/api/reports/list")
async def list_reports():
    reports = []
    for f in sorted(Path(settings.REPORT_DIR).iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix in (".xlsx", ".html"):
            reports.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
    return reports


# ══════════════════════════════════════════════════════════════════════════════
# API: AI 对话（REST）
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat_rest(req: ChatRequest):
    sid = req.session_id or dialog_handler.new_session()
    reply = await dialog_handler.chat(sid, req.message)
    return ChatResponse(reply=reply, session_id=sid)


@app.delete("/api/chat/{session_id}")
async def clear_chat(session_id: str):
    dialog_handler.clear_session(session_id)
    return {"status": "cleared"}


# ══════════════════════════════════════════════════════════════════════════════
# WebSocket: 实时对话
# ══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    await ws_manager.connect(ws, session_id)
    if session_id not in dialog_handler.sessions:
        dialog_handler.new_session(session_id)
    logger.info(f"WebSocket 连接: {session_id}")
    try:
        while True:
            data = await ws.receive_json()
            user_msg = data.get("message", "")
            if not user_msg:
                continue
            # 发送"正在输入"状态
            await ws.send_json({"type": "typing", "status": True})
            try:
                reply = await dialog_handler.chat(session_id, user_msg)
                await ws.send_json({"type": "message", "role": "assistant", "content": reply})
            except Exception as e:
                logger.error(f"对话错误: {e}")
                await ws.send_json({"type": "error", "content": f"处理失败: {str(e)}"})
            finally:
                await ws.send_json({"type": "typing", "status": False})
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
        logger.info(f"WebSocket 断开: {session_id}")


# ══════════════════════════════════════════════════════════════════════════════
# Webhook: 微信企业号消息接收
# ══════════════════════════════════════════════════════════════════════════════

async def handle_wechat_message(msg: WeChatMessage):
    """处理微信消息，支持数据查询和文件接收"""
    if msg.msg_type.value == "file" and msg.media_id:
        save_path = os.path.join(settings.UPLOAD_DIR, f"wx_{msg.media_id}.xlsx")
        ok = await wechat_receiver.download_media(msg.media_id, save_path)
        if ok:
            proc = ExcelProcessor()
            proc.load_file(save_path)
            clean_df = proc.clean()
            market_analyzer.set_data(clean_df)
            summary = proc.get_summary()
            reply = f"✅ 数据文件已导入！\n共 {summary.get('total_rows', 0)} 条记录"
            await wechat_receiver.send_text(msg.from_user, reply)
    else:
        sid = f"wx_{msg.from_user}"
        reply = await dialog_handler.chat(sid, msg.content)
        await wechat_receiver.send_text(msg.from_user, reply)


wechat_receiver.register_handler(handle_wechat_message)


@app.get("/webhook/wechat")
async def wechat_verify(msg_signature: str, timestamp: str, nonce: str, echostr: str = ""):
    if wechat_receiver.verify_signature(msg_signature, timestamp, nonce, echostr):
        return HTMLResponse(echostr)
    raise HTTPException(403, "验签失败")


@app.post("/webhook/wechat")
async def wechat_receive(request: Request):
    body = await request.body()
    try:
        msg = wechat_receiver.parse_xml_message(body.decode("utf-8"))
        await wechat_receiver.dispatch(msg)
    except Exception as e:
        logger.error(f"微信消息处理错误: {e}")
    return HTMLResponse("success")


# ══════════════════════════════════════════════════════════════════════════════
# Webhook: 钉钉消息接收
# ══════════════════════════════════════════════════════════════════════════════

async def handle_dingtalk_message(msg: DingTalkMessage):
    sid = f"dd_{msg.sender_id}"
    reply = await dialog_handler.chat(sid, msg.content)
    await dingtalk_receiver.send_robot_markdown(
        title="营销助手回复",
        content=reply
    )


dingtalk_receiver.register_handler(handle_dingtalk_message)


@app.post("/webhook/dingtalk")
async def dingtalk_receive(request: Request):
    try:
        timestamp = request.headers.get("timestamp", "")
        sign = request.headers.get("sign", "")
        body = await request.json()
        msg = dingtalk_receiver.parse_webhook_message(body)
        await dingtalk_receiver.dispatch(msg)
        return {"msgtype": "text", "text": {"content": "处理中..."}}
    except Exception as e:
        logger.error(f"钉钉消息处理错误: {e}")
        return {"msgtype": "text", "text": {"content": "处理失败"}}


# ══════════════════════════════════════════════════════════════════════════════
# API: 系统信息
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    has_data = market_analyzer.df is not None and not market_analyzer.df.empty
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "has_data": has_data,
        "data_rows": len(market_analyzer.df) if has_data else 0,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/system/summary")
async def system_summary():
    has_data = market_analyzer.df is not None and not market_analyzer.df.empty
    return {
        "app_name": settings.APP_NAME,
        "has_data": has_data,
        "data_rows": len(market_analyzer.df) if has_data else 0,
        "columns": list(market_analyzer.df.columns) if has_data else [],
        "report_count": len(list(Path(settings.REPORT_DIR).glob("*.*"))),
        "upload_count": len(list(Path(settings.UPLOAD_DIR).glob("*.*")))
    }
