"""
报表生成模块
Report Generation Module

支持：PDF 报表、Excel 多Sheet报表、HTML 可视化报表
"""
import os
import io
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from config import settings
from modules.analysis.market_analysis import MarketAnalyzer

# ── 中文字体配置 ───────────────────────────────────────────────────────────────
def _setup_chinese_font():
    """尝试设置中文字体（matplotlib）"""
    font_candidates = [
        "SimHei", "Microsoft YaHei", "WenQuanYi Zen Hei",
        "Noto Sans CJK SC", "PingFang SC", "STHeiti"
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in font_candidates:
        if font in available:
            plt.rcParams["font.sans-serif"] = [font]
            plt.rcParams["axes.unicode_minus"] = False
            return font
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    return "DejaVu Sans"


FONT_NAME = _setup_chinese_font()


class ReportGenerator:
    """多格式报表生成器"""

    def __init__(self, analyzer: MarketAnalyzer):
        self.analyzer = analyzer
        os.makedirs(settings.REPORT_DIR, exist_ok=True)

    def _ts(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Excel 多维报表
    # ─────────────────────────────────────────────────────────────────────────
    def generate_excel_report(self, title: str = "营销数据分析报告",
                               date_from: Optional[str] = None,
                               date_to: Optional[str] = None) -> str:
        filename = f"marketing_report_{self._ts()}.xlsx"
        output_path = os.path.join(settings.REPORT_DIR, filename)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Sheet 1: KPI 总览
            kpi = self.analyzer.overall_kpi(date_from, date_to)
            kpi_df = pd.DataFrame([
                {"指标": k, "数值": v} for k, v in kpi.items()
            ])
            kpi_df.to_excel(writer, sheet_name="KPI总览", index=False)

            # Sheet 2: 销售趋势（月度）
            trend = self.analyzer.sales_trend("ME", date_from, date_to)
            if trend:
                trend_df = pd.DataFrame(trend)
                trend_df.columns = ["时间", "销售额", "环比%"]
                trend_df.to_excel(writer, sheet_name="月度趋势", index=False)

            # Sheet 3: 产品分析
            prod = self.analyzer.product_analysis(date_from=date_from, date_to=date_to)
            if prod.get("top_by_sales"):
                pd.DataFrame(prod["top_by_sales"]).to_excel(
                    writer, sheet_name="产品排行", index=False
                )

            # Sheet 4: 区域分析
            region = self.analyzer.region_analysis(date_from=date_from, date_to=date_to)
            if region:
                pd.DataFrame(region).to_excel(writer, sheet_name="区域分析", index=False)

            # Sheet 5: 渠道分析
            channel = self.analyzer.channel_analysis(date_from=date_from, date_to=date_to)
            if channel:
                pd.DataFrame(channel).to_excel(writer, sheet_name="渠道分析", index=False)

            # Sheet 6: 客户 RFM
            rfm = self.analyzer.rfm_analysis()
            if rfm:
                pd.DataFrame(rfm).to_excel(writer, sheet_name="客户RFM", index=False)

            # Sheet 7: 同比环比
            yoy = self.analyzer.yoy_mom_comparison()
            if yoy:
                pd.DataFrame([yoy]).to_excel(writer, sheet_name="同比环比", index=False)

            # Sheet 8: 销售预测
            forecast = self.analyzer.simple_forecast(periods=6)
            if forecast:
                pd.DataFrame(forecast).to_excel(writer, sheet_name="销售预测", index=False)

            # Sheet 9: 原始数据
            if self.analyzer.df is not None:
                self.analyzer.df.to_excel(writer, sheet_name="原始数据", index=False)

        logger.info(f"Excel 报表已生成: {output_path}")
        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # 2. HTML 可视化报表（Plotly）
    # ─────────────────────────────────────────────────────────────────────────
    def generate_html_report(self, title: str = "营销数据分析报告",
                              date_from: Optional[str] = None,
                              date_to: Optional[str] = None) -> str:
        filename = f"report_{self._ts()}.html"
        output_path = os.path.join(settings.REPORT_DIR, filename)
        charts_html = []

        # KPI 卡片
        kpi = self.analyzer.overall_kpi(date_from, date_to)
        kpi_items = "".join(
            f'<div class="kpi-card"><div class="kpi-value">{v:,.2f}</div>'
            f'<div class="kpi-label">{k}</div></div>'
            for k, v in kpi.items() if isinstance(v, (int, float))
        )

        # 趋势折线图
        trend = self.analyzer.sales_trend("ME", date_from, date_to)
        if trend:
            fig = go.Figure()
            periods = [t["period"] for t in trend]
            sales_vals = [t["sales"] for t in trend]
            fig.add_trace(go.Scatter(
                x=periods, y=sales_vals, mode="lines+markers",
                name="月度销售额",
                line=dict(color="#1890ff", width=2),
                marker=dict(size=6)
            ))
            fig.update_layout(
                title="月度销售趋势", xaxis_title="时间", yaxis_title="销售额",
                template="plotly_white", height=350
            )
            charts_html.append(fig.to_html(full_html=False, include_plotlyjs="cdn"))

        # 产品排行柱状图
        prod = self.analyzer.product_analysis(10, date_from, date_to)
        if prod.get("top_by_sales"):
            df_prod = pd.DataFrame(prod["top_by_sales"]).head(10)
            fig = px.bar(
                df_prod, x="sales", y="product",
                orientation="h", title="产品销售额 Top 10",
                color="sales", color_continuous_scale="Blues"
            )
            fig.update_layout(template="plotly_white", height=400)
            charts_html.append(fig.to_html(full_html=False, include_plotlyjs=False))

        # 区域饼图
        region = self.analyzer.region_analysis(date_from=date_from, date_to=date_to)
        if region:
            df_region = pd.DataFrame(region)
            fig = px.pie(
                df_region, values="sales", names="region",
                title="区域销售占比", hole=0.35
            )
            fig.update_layout(template="plotly_white", height=380)
            charts_html.append(fig.to_html(full_html=False, include_plotlyjs=False))

        # 渠道分析
        channel = self.analyzer.channel_analysis(date_from, date_to)
        if channel:
            df_ch = pd.DataFrame(channel)
            fig = px.bar(
                df_ch, x="channel", y="sales",
                title="销售渠道对比", color="channel",
                text_auto=".2s"
            )
            fig.update_layout(template="plotly_white", height=350)
            charts_html.append(fig.to_html(full_html=False, include_plotlyjs=False))

        # 预测
        forecast = self.analyzer.simple_forecast(6)
        if forecast and trend:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=periods, y=sales_vals,
                mode="lines+markers", name="历史销售",
                line=dict(color="#1890ff")
            ))
            f_periods = [f["period"] for f in forecast]
            f_vals = [f["forecast_sales"] for f in forecast]
            fig.add_trace(go.Scatter(
                x=f_periods, y=f_vals,
                mode="lines+markers", name="预测",
                line=dict(color="#f5222d", dash="dash")
            ))
            fig.update_layout(
                title="销售预测（未来6期）", template="plotly_white", height=350
            )
            charts_html.append(fig.to_html(full_html=False, include_plotlyjs=False))

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f7fa; margin: 0; padding: 20px; }}
  h1 {{ color: #1a1a2e; text-align: center; margin-bottom: 30px; }}
  .meta {{ text-align: center; color: #888; margin-bottom: 20px; }}
  .kpi-row {{ display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; margin: 24px 0; }}
  .kpi-card {{ background: #fff; border-radius: 12px; padding: 20px 28px;
               box-shadow: 0 2px 12px rgba(0,0,0,.08); min-width: 140px; text-align: center; }}
  .kpi-value {{ font-size: 1.8rem; font-weight: 700; color: #1890ff; }}
  .kpi-label {{ font-size: 0.85rem; color: #888; margin-top: 6px; text-transform: capitalize; }}
  .chart-card {{ background: #fff; border-radius: 12px; padding: 16px;
                 box-shadow: 0 2px 12px rgba(0,0,0,.08); margin: 16px 0; }}
  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media(max-width:768px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
  footer {{ text-align: center; color: #aaa; margin-top: 40px; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
{'日期范围：' + (date_from or '全部') + ' ~ ' + (date_to or '全部')}</p>

<div class="kpi-row">{kpi_items}</div>

<div class="charts-grid">
{"".join(f'<div class="chart-card">{c}</div>' for c in charts_html)}
</div>

<footer>由 智能营销业务系统 自动生成 · {datetime.now().year}</footer>
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML 报表已生成: {output_path}")
        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # 3. 快速摘要文本（用于消息推送）
    # ─────────────────────────────────────────────────────────────────────────
    def generate_text_summary(self, period_label: str = "本月") -> str:
        try:
            kpi = self.analyzer.overall_kpi()
            yoy = self.analyzer.yoy_mom_comparison()
            lines = [
                f"📊 **{period_label}营销数据摘要**",
                f"🔹 总销售额：¥{kpi.get('total_sales', 0):,.2f}",
                f"🔹 订单数量：{kpi.get('order_count', 0):,}",
                f"🔹 总利润：¥{kpi.get('total_profit', 0):,.2f}",
                f"🔹 利润率：{kpi.get('avg_profit_rate', 0):.1f}%",
                f"🔹 活跃客户：{kpi.get('unique_customers', 0):,}",
            ]
            if yoy:
                mom = yoy.get("mom_pct")
                yoy_pct = yoy.get("yoy_pct")
                if mom is not None:
                    arrow = "▲" if mom > 0 else "▼"
                    lines.append(f"📈 环比：{arrow} {abs(mom):.1f}%")
                if yoy_pct is not None:
                    arrow = "▲" if yoy_pct > 0 else "▼"
                    lines.append(f"📈 同比：{arrow} {abs(yoy_pct):.1f}%")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return "数据摘要生成失败，请检查数据"
