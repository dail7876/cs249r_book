"""
API 路由
FastAPI Routes
"""
import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Request, UploadFile, BackgroundTasks, Query
)
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from ..config import (
    UPLOAD_DIR, REPORTS_DIR, KPI_TARGETS, SUPPORTED_FORMATS,
    WECHAT_TOKEN
)
from ..database import (
    get_session, SalesRecord, IncomingMessage, DataSource, MessageStatus
)
from ..data_processing import DataProcessor, MarketAnalyzer, ReportGenerator
from ..ai import ConversationEngine
from .models import (
    ChatRequest, ChatResponse, SalesQueryRequest, AnalysisRequest,
    ReportRequest, DataUploadResponse, KPIResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── 全局分析器（运行时注入）─────────────────────────────────
_analyzer: Optional[MarketAnalyzer] = None
_reporter: Optional[ReportGenerator] = None
_conversation: Optional[ConversationEngine] = None
_processor: Optional[DataProcessor] = None


def init_services(analyzer: MarketAnalyzer, reporter: ReportGenerator,
                  conversation: ConversationEngine, processor: DataProcessor):
    global _analyzer, _reporter, _conversation, _processor
    _analyzer = analyzer
    _reporter = reporter
    _conversation = conversation
    _processor = processor


# ─── 对话接口 ────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, tags=["对话"])
async def chat(request: ChatRequest):
    """自然语言对话接口"""
    if _conversation is None:
        raise HTTPException(status_code=503, detail="对话服务未初始化")
    result = await _conversation.chat(request.message, request.session_id)
    return ChatResponse(**result)


@router.delete("/chat/{session_id}", tags=["对话"])
async def clear_session(session_id: str):
    """清除对话会话历史"""
    if _conversation:
        _conversation.clear_session(session_id)
    return {"success": True, "message": "会话已清除"}


# ─── 数据上传 ─────────────────────────────────────────────────

@router.post("/upload", response_model=DataUploadResponse, tags=["数据管理"])
async def upload_data(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """上传数据文件（Excel/CSV）"""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {suffix}，支持: {SUPPORTED_FORMATS}"
        )

    dest = UPLOAD_DIR / file.filename
    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")

    # 后台处理数据
    background_tasks.add_task(_process_uploaded_file, str(dest), db)

    # 同步获取摘要
    if _processor:
        df = _processor.process_file(str(dest))
        if df is not None:
            summary = _processor.get_summary(df)
            if _analyzer:
                _analyzer.set_data(df)
            return DataUploadResponse(
                success=True,
                message=f"文件上传成功，正在后台导入数据库",
                summary=summary,
                records_imported=len(df),
            )

    return DataUploadResponse(
        success=True,
        message="文件已上传，正在后台处理",
    )


async def _process_uploaded_file(filepath: str, db: Session):
    """后台任务：处理上传的文件并导入数据库"""
    try:
        if _processor is None:
            return
        df = _processor.process_file(filepath)
        if df is None:
            return

        records = _processor.to_sales_records(df)
        for rec in records:
            db_record = SalesRecord(**rec, source=DataSource.UPLOAD)
            db.add(db_record)
        db.commit()
        logger.info(f"导入 {len(records)} 条销售记录")

        if _analyzer:
            _analyzer.set_data(df)
    except Exception as e:
        logger.error(f"后台文件处理失败: {e}")
        db.rollback()


# ─── 数据查询 ─────────────────────────────────────────────────

@router.get("/sales", tags=["数据查询"])
async def get_sales(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """查询销售记录"""
    query = db.query(SalesRecord)

    if start_date:
        query = query.filter(SalesRecord.date >= start_date)
    if end_date:
        query = query.filter(SalesRecord.date <= end_date)
    if region:
        query = query.filter(SalesRecord.region == region)
    if category:
        query = query.filter(SalesRecord.category == category)
    if channel:
        query = query.filter(SalesRecord.sales_channel == channel)

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "records": [
            {
                "id": r.id,
                "date": r.date.isoformat() if r.date else None,
                "product_name": r.product_name,
                "category": r.category,
                "region": r.region,
                "sales_channel": r.sales_channel,
                "quantity": r.quantity,
                "unit_price": r.unit_price,
                "total_amount": r.total_amount,
                "profit": r.profit,
                "profit_margin": r.profit_margin,
                "customer_name": r.customer_name,
                "salesperson": r.salesperson,
            }
            for r in records
        ],
    }


# ─── 分析接口 ─────────────────────────────────────────────────

@router.post("/analyze", tags=["市场分析"])
async def analyze(request: AnalysisRequest):
    """执行市场分析"""
    if _analyzer is None:
        raise HTTPException(status_code=503, detail="分析引擎未初始化，请先上传数据")

    atype = request.analysis_type
    params = request.params

    try:
        if atype == "sales_trend":
            df = _analyzer.sales_trend(**params)
            return {"type": atype, "data": df.to_dict(orient="records")}

        elif atype == "region":
            df = _analyzer.region_analysis(**params)
            return {"type": atype, "data": df.to_dict(orient="records")}

        elif atype == "product":
            df = _analyzer.product_analysis(**params)
            return {"type": atype, "data": df.to_dict(orient="records")}

        elif atype == "rfm":
            df = _analyzer.rfm_analysis()
            segment_counts = df["segment"].value_counts().to_dict()
            return {
                "type": atype,
                "data": df.head(50).to_dict(orient="records"),
                "segment_summary": segment_counts,
            }

        elif atype == "channel":
            df = _analyzer.channel_analysis(**params)
            return {"type": atype, "data": df.to_dict(orient="records")}

        elif atype == "kpi":
            result = _analyzer.kpi_analysis(KPI_TARGETS, **params)
            return {"type": atype, "data": result}

        elif atype == "summary":
            result = _analyzer.generate_summary()
            return {"type": atype, "data": result}

        else:
            raise HTTPException(status_code=400, detail=f"未知分析类型: {atype}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── 报表接口 ─────────────────────────────────────────────────

@router.post("/report", tags=["报表"])
async def generate_report(request: ReportRequest):
    """生成报表"""
    if _analyzer is None or _reporter is None:
        raise HTTPException(status_code=503, detail="服务未初始化，请先上传数据")

    try:
        summary = _analyzer.generate_summary()

        if request.report_format == "html":
            path = _reporter.generate_html_report(request.title, summary)
            return {"success": True, "format": "html", "path": path,
                    "download_url": f"/api/report/download/{Path(path).name}"}

        elif request.report_format == "excel":
            sheets = {}
            if "sales_trend" in request.analysis_types:
                df = _analyzer.sales_trend(freq="M")
                if not df.empty:
                    sheets["月度趋势"] = df
            if "region" in request.analysis_types:
                df = _analyzer.region_analysis()
                if not df.empty:
                    sheets["区域分析"] = df
            if "product" in request.analysis_types:
                df = _analyzer.product_analysis(top_n=20)
                if not df.empty:
                    sheets["产品分析"] = df
            if "channel" in request.analysis_types:
                df = _analyzer.channel_analysis()
                if not df.empty:
                    sheets["渠道分析"] = df

            if not sheets:
                sheets["数据摘要"] = pd.DataFrame([summary.get("basic", {})])

            path = _reporter.generate_excel_report(request.title, sheets)
            return {"success": True, "format": "excel", "path": path,
                    "download_url": f"/api/report/download/{Path(path).name}"}

        else:
            raise HTTPException(status_code=400, detail="不支持的报表格式")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"报表生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/download/{filename}", tags=["报表"])
async def download_report(filename: str):
    """下载报表文件"""
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="报表文件不存在")
    return FileResponse(
        str(filepath),
        media_type="application/octet-stream",
        filename=filename,
    )


@router.get("/report/view/{filename}", tags=["报表"], response_class=HTMLResponse)
async def view_report(filename: str):
    """在线查看 HTML 报表"""
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="报表文件不存在")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


# ─── 微信 Webhook ─────────────────────────────────────────────

@router.get("/webhook/wechat", tags=["Webhook"])
async def wechat_verify(
    signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
):
    """微信服务器验证"""
    import hashlib
    params = sorted([WECHAT_TOKEN, timestamp, nonce])
    computed = hashlib.sha1("".join(params).encode()).hexdigest()
    if computed == signature:
        return HTMLResponse(content=echostr)
    raise HTTPException(status_code=403, detail="签名验证失败")


@router.post("/webhook/wechat", tags=["Webhook"])
async def wechat_message(request: Request, background_tasks: BackgroundTasks):
    """接收微信消息"""
    body = await request.body()
    msg_data = {"raw": body.decode("utf-8"), "source": "wechat"}
    background_tasks.add_task(_handle_incoming_message, msg_data)
    return HTMLResponse(content="success")


# ─── 钉钉 Webhook ─────────────────────────────────────────────

@router.post("/webhook/dingtalk", tags=["Webhook"])
async def dingtalk_message(request: Request, background_tasks: BackgroundTasks):
    """接收钉钉机器人消息"""
    payload = await request.json()
    msg_type = payload.get("msgtype", "")
    text = ""
    if msg_type == "text":
        text = payload.get("text", {}).get("content", "").strip()

    if _conversation and text:
        result = await _conversation.chat(text)
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": "分析结果",
                "text": result.get("reply", "处理中...")
            }
        }

    return {"msgtype": "text", "text": {"content": "消息已收到"}}


# ─── 邮件 Webhook（POST 接口，供邮件网关调用）────────────────

@router.post("/webhook/email", tags=["Webhook"])
async def email_message(request: Request, background_tasks: BackgroundTasks):
    """接收邮件网关推送（如 SendGrid Inbound Parse）"""
    form = await request.form()
    subject = form.get("subject", "")
    sender = form.get("from", "")
    text_body = form.get("text", "")

    msg_data = {
        "source": "email",
        "subject": subject,
        "sender": sender,
        "body": text_body,
    }
    background_tasks.add_task(_handle_incoming_message, msg_data)
    return {"success": True}


# ─── 系统状态 ─────────────────────────────────────────────────

@router.get("/status", tags=["系统"])
async def system_status():
    """系统运行状态"""
    has_data = _analyzer is not None and _analyzer.df is not None
    return {
        "status": "running",
        "data_loaded": has_data,
        "analyzer_ready": _analyzer is not None,
        "conversation_ready": _conversation is not None,
        "reporter_ready": _reporter is not None,
    }


# ─── 内部辅助 ─────────────────────────────────────────────────

async def _handle_incoming_message(msg_data: Dict[str, Any]):
    """处理接收到的消息（后台任务）"""
    logger.info(f"处理消息: source={msg_data.get('source')}")
    # 可扩展：解析附件、触发分析、回复消息等
