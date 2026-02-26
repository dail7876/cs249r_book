"""
报表生成模块
Report Generator

支持输出格式:
- HTML 报表（含图表）
- Excel 报表
- JSON 数据摘要
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报表生成器"""

    def __init__(self, reports_dir: str = "/tmp/reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------
    # HTML 报表
    # ----------------------------------------------------------

    def generate_html_report(self, title: str, summary: Dict[str, Any],
                              analysis_results: Dict[str, pd.DataFrame] = None,
                              filename: str = None) -> str:
        """生成 HTML 报表，返回文件路径"""
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{ts}.html"

        filepath = self.reports_dir / filename
        html = self._build_html(title, summary, analysis_results)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML 报表已生成: {filepath}")
        return str(filepath)

    def _build_html(self, title: str, summary: Dict[str, Any],
                    analysis_results: Dict[str, pd.DataFrame] = None) -> str:
        """构建 HTML 内容"""
        basic = summary.get("basic", {})
        total_revenue = basic.get("total_revenue", 0)
        total_profit = basic.get("total_profit", 0)
        avg_margin = basic.get("avg_profit_margin", 0)
        total_records = basic.get("total_records", 0)

        # KPI 卡片
        kpi_cards = f"""
        <div class="kpi-grid">
            <div class="kpi-card blue">
                <div class="kpi-label">总销售额</div>
                <div class="kpi-value">¥{total_revenue:,.0f}</div>
            </div>
            <div class="kpi-card green">
                <div class="kpi-label">总利润</div>
                <div class="kpi-value">¥{total_profit:,.0f}</div>
            </div>
            <div class="kpi-card orange">
                <div class="kpi-label">平均利润率</div>
                <div class="kpi-value">{avg_margin*100:.1f}%</div>
            </div>
            <div class="kpi-card purple">
                <div class="kpi-label">数据记录数</div>
                <div class="kpi-value">{total_records:,}</div>
            </div>
        </div>"""

        # 趋势数据（Chart.js）
        trend_data = summary.get("monthly_trend", [])
        trend_labels = json.dumps([r.get("period_str", "") for r in trend_data])
        trend_revenue = json.dumps([round(r.get("total_amount", 0), 2) for r in trend_data])
        trend_profit = json.dumps([round(r.get("total_profit", 0), 2) for r in trend_data])

        # 区域数据
        regions = summary.get("top_regions", [])
        region_labels = json.dumps([r.get("region", "") for r in regions])
        region_values = json.dumps([round(r.get("total_amount", 0), 2) for r in regions])

        # 产品数据
        products = summary.get("top_products", [])
        product_labels = json.dumps([r.get("product_name", r.get("category", "")) for r in products])
        product_values = json.dumps([round(r.get("total_amount", 0), 2) for r in products])

        # 区域表格
        region_rows = ""
        for r in regions:
            region_rows += f"""
            <tr>
                <td>{r.get('region','')}</td>
                <td>¥{r.get('total_amount',0):,.0f}</td>
                <td>¥{r.get('total_profit',0):,.0f}</td>
                <td>{r.get('revenue_share',0):.1f}%</td>
                <td>{r.get('avg_profit_margin',0)*100:.1f}%</td>
            </tr>"""

        # 产品表格
        product_rows = ""
        for p in products:
            product_rows += f"""
            <tr>
                <td>{p.get('product_name', p.get('category',''))}</td>
                <td>{p.get('total_quantity',0):,}</td>
                <td>¥{p.get('total_amount',0):,.0f}</td>
                <td>¥{p.get('total_profit',0):,.0f}</td>
                <td>{p.get('revenue_share',0):.1f}%</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --blue: #1a73e8; --green: #34a853; --orange: #fb8c00; --purple: #9c27b0;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f0f2f5; color: #333; }}
  .header {{
    background: linear-gradient(135deg, var(--blue), #0d47a1);
    color: white; padding: 30px 40px;
  }}
  .header h1 {{ font-size: 28px; }}
  .header .sub {{ opacity: 0.8; margin-top: 8px; font-size: 14px; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 30px 20px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
  .kpi-card {{
    background: white; border-radius: 12px; padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    border-left: 5px solid;
  }}
  .kpi-card.blue {{ border-color: var(--blue); }}
  .kpi-card.green {{ border-color: var(--green); }}
  .kpi-card.orange {{ border-color: var(--orange); }}
  .kpi-card.purple {{ border-color: var(--purple); }}
  .kpi-label {{ font-size: 13px; color: #888; margin-bottom: 10px; }}
  .kpi-value {{ font-size: 26px; font-weight: bold; color: #333; }}
  .charts-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 30px; }}
  .chart-card {{
    background: white; border-radius: 12px; padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}
  .chart-card h3 {{ font-size: 16px; color: #555; margin-bottom: 20px; }}
  .tables-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .table-card {{
    background: white; border-radius: 12px; padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}
  .table-card h3 {{ font-size: 16px; color: #555; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: var(--blue); color: white; padding: 10px 12px; text-align: left; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #f8f9fa; }}
  .footer {{ text-align: center; padding: 20px; color: #aaa; font-size: 12px; }}
  @media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .charts-grid, .tables-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 {title}</h1>
  <div class="sub">生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')} | 自动化业务分析系统</div>
</div>
<div class="container">
  {kpi_cards}

  <div class="charts-grid">
    <div class="chart-card">
      <h3>📈 月度销售趋势</h3>
      <canvas id="trendChart" height="80"></canvas>
    </div>
    <div class="chart-card">
      <h3>🗺 区域销售占比</h3>
      <canvas id="regionChart"></canvas>
    </div>
  </div>

  <div class="charts-grid">
    <div class="chart-card">
      <h3>📦 产品销售排名</h3>
      <canvas id="productChart" height="80"></canvas>
    </div>
    <div class="chart-card">
      <h3>📊 利润趋势</h3>
      <canvas id="profitChart"></canvas>
    </div>
  </div>

  <div class="tables-grid">
    <div class="table-card">
      <h3>🗺 区域销售明细</h3>
      <table>
        <tr><th>区域</th><th>销售额</th><th>利润</th><th>占比</th><th>利润率</th></tr>
        {region_rows or '<tr><td colspan="5">暂无数据</td></tr>'}
      </table>
    </div>
    <div class="table-card">
      <h3>📦 产品销售明细</h3>
      <table>
        <tr><th>产品</th><th>数量</th><th>销售额</th><th>利润</th><th>占比</th></tr>
        {product_rows or '<tr><td colspan="5">暂无数据</td></tr>'}
      </table>
    </div>
  </div>
</div>

<div class="footer">本报告由自动化业务系统生成 · Powered by AI Analytics</div>

<script>
const BLUE = '#1a73e8', GREEN = '#34a853', ORANGE = '#fb8c00', PURPLE = '#9c27b0';

// 月度趋势
new Chart(document.getElementById('trendChart'), {{
  type: 'bar',
  data: {{
    labels: {trend_labels},
    datasets: [
      {{ label: '销售额', data: {trend_revenue}, backgroundColor: BLUE + '99', borderColor: BLUE, borderWidth: 2, yAxisID: 'y' }},
      {{ label: '利润', data: {trend_profit}, type: 'line', borderColor: GREEN, backgroundColor: GREEN + '22', borderWidth: 2, yAxisID: 'y', tension: 0.4 }}
    ]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ position: 'top' }} }} }}
}});

// 区域饼图
new Chart(document.getElementById('regionChart'), {{
  type: 'doughnut',
  data: {{
    labels: {region_labels},
    datasets: [{{ data: {region_values}, backgroundColor: [BLUE, GREEN, ORANGE, PURPLE, '#f44336', '#00bcd4', '#8bc34a'] }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});

// 产品条形图
new Chart(document.getElementById('productChart'), {{
  type: 'bar',
  data: {{
    labels: {product_labels},
    datasets: [{{ label: '销售额', data: {product_values}, backgroundColor: ORANGE + 'CC' }}]
  }},
  options: {{ indexAxis: 'y', responsive: true }}
}});

// 利润折线图
new Chart(document.getElementById('profitChart'), {{
  type: 'line',
  data: {{
    labels: {trend_labels},
    datasets: [{{ label: '利润', data: {trend_profit}, borderColor: GREEN, backgroundColor: GREEN + '22', fill: true, tension: 0.4 }}]
  }},
  options: {{ responsive: true }}
}});
</script>
</body>
</html>"""

    # ----------------------------------------------------------
    # Excel 报表
    # ----------------------------------------------------------

    def generate_excel_report(self, title: str,
                               sheets: Dict[str, pd.DataFrame],
                               filename: str = None) -> str:
        """生成 Excel 报表，返回文件路径"""
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{ts}.xlsx"

        filepath = self.reports_dir / filename
        with pd.ExcelWriter(str(filepath), engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

        logger.info(f"Excel 报表已生成: {filepath}")
        return str(filepath)

    # ----------------------------------------------------------
    # 快速文本摘要（用于聊天回复）
    # ----------------------------------------------------------

    def generate_text_summary(self, summary: Dict[str, Any]) -> str:
        """生成纯文本摘要（适合聊天消息）"""
        basic = summary.get("basic", {})
        lines = [
            "📊 **业务数据摘要**",
            f"• 总销售额: ¥{basic.get('total_revenue', 0):,.0f}",
            f"• 总利润: ¥{basic.get('total_profit', 0):,.0f}",
            f"• 平均利润率: {basic.get('avg_profit_margin', 0)*100:.1f}%",
            f"• 数据记录: {basic.get('total_records', 0):,} 条",
        ]

        regions = summary.get("top_regions", [])
        if regions:
            lines.append("\n🗺 **TOP 区域**")
            for r in regions[:3]:
                lines.append(f"  {r.get('region','')}: ¥{r.get('total_amount',0):,.0f}")

        products = summary.get("top_products", [])
        if products:
            lines.append("\n📦 **TOP 产品**")
            for p in products[:3]:
                name = p.get("product_name", p.get("category", ""))
                lines.append(f"  {name}: ¥{p.get('total_amount',0):,.0f}")

        return "\n".join(lines)
