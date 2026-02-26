"""
API 数据模型（Pydantic）
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，不传则新建")
    source: str = Field("web", description="消息来源: web/wechat/dingtalk/email")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    data_result: Optional[Dict[str, Any]] = None
    timestamp: str


class SalesQueryRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    region: Optional[str] = None
    category: Optional[str] = None
    channel: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)


class AnalysisRequest(BaseModel):
    analysis_type: str = Field(
        ...,
        description="分析类型: sales_trend/region/product/rfm/channel/kpi/summary"
    )
    params: Dict[str, Any] = Field(default_factory=dict)


class ReportRequest(BaseModel):
    title: str = Field("业务分析报告", description="报表标题")
    report_format: str = Field("html", description="输出格式: html/excel")
    analysis_types: List[str] = Field(
        default_factory=lambda: ["summary"],
        description="包含的分析类型"
    )
    params: Dict[str, Any] = Field(default_factory=dict)


class DataUploadResponse(BaseModel):
    success: bool
    message: str
    summary: Optional[Dict[str, Any]] = None
    records_imported: int = 0


class KPIResponse(BaseModel):
    period: str
    kpis: Dict[str, Any]


class WebhookVerifyResponse(BaseModel):
    echostr: Optional[str] = None
    success: bool = True
