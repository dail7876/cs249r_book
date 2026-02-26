"""
市场分析引擎
Market Analysis Engine

分析维度:
- 销售趋势分析
- 区域市场分析
- 产品品类分析
- 客户价值分析 (RFM)
- 渠道效益分析
- KPI 达成分析
- 竞品对比（占位）
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MarketAnalyzer:
    """市场分析引擎"""

    def __init__(self, df: pd.DataFrame = None):
        self.df = df

    def set_data(self, df: pd.DataFrame):
        self.df = df

    # ----------------------------------------------------------
    # 销售趋势分析
    # ----------------------------------------------------------

    def sales_trend(self, freq: str = "M",
                    start_date: str = None,
                    end_date: str = None) -> pd.DataFrame:
        """销售趋势分析（按时间聚合）

        freq: 'D'=日, 'W'=周, 'M'=月, 'Q'=季度, 'Y'=年
        """
        df = self._filter_date(start_date, end_date)
        if "date" not in df.columns or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df["period"] = df["date"].dt.to_period(freq)
        grouped = df.groupby("period").agg(
            total_amount=("total_amount", "sum"),
            total_profit=("profit", "sum"),
            order_count=("quantity", "count"),
            avg_order_value=("total_amount", "mean"),
        ).reset_index()
        grouped["growth_rate"] = grouped["total_amount"].pct_change() * 100
        grouped["period_str"] = grouped["period"].astype(str)
        return grouped

    # ----------------------------------------------------------
    # 区域分析
    # ----------------------------------------------------------

    def region_analysis(self, start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
        """区域市场分析"""
        df = self._filter_date(start_date, end_date)
        if "region" not in df.columns or df.empty:
            return pd.DataFrame()

        result = df.groupby("region").agg(
            total_amount=("total_amount", "sum"),
            total_profit=("profit", "sum"),
            order_count=("quantity", "count"),
            avg_profit_margin=("profit_margin", "mean"),
            customer_count=("customer_id", "nunique"),
        ).reset_index()
        result["revenue_share"] = (
            result["total_amount"] / result["total_amount"].sum() * 100
        )
        return result.sort_values("total_amount", ascending=False)

    # ----------------------------------------------------------
    # 产品品类分析
    # ----------------------------------------------------------

    def product_analysis(self, top_n: int = 10,
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """产品/品类销售分析"""
        df = self._filter_date(start_date, end_date)
        col = "product_name" if "product_name" in df.columns else "category"
        if col not in df.columns or df.empty:
            return pd.DataFrame()

        result = df.groupby(col).agg(
            total_amount=("total_amount", "sum"),
            total_quantity=("quantity", "sum"),
            total_profit=("profit", "sum"),
            avg_unit_price=("unit_price", "mean"),
            avg_profit_margin=("profit_margin", "mean"),
        ).reset_index()
        result["revenue_share"] = (
            result["total_amount"] / result["total_amount"].sum() * 100
        )
        return result.nlargest(top_n, "total_amount")

    # ----------------------------------------------------------
    # RFM 客户价值分析
    # ----------------------------------------------------------

    def rfm_analysis(self, reference_date: datetime = None) -> pd.DataFrame:
        """RFM 客户价值分析

        R (Recency)  : 最近购买时间
        F (Frequency): 购买频次
        M (Monetary) : 消费金额
        """
        df = self.df.copy()
        if "customer_id" not in df.columns or df.empty:
            return pd.DataFrame()

        if reference_date is None:
            reference_date = df["date"].max() + timedelta(days=1)

        rfm = df.groupby("customer_id").agg(
            recency=("date", lambda x: (reference_date - x.max()).days),
            frequency=("date", "count"),
            monetary=("total_amount", "sum"),
        ).reset_index()

        # 分位数评分 (1-5)
        for col, ascending in [("recency", True), ("frequency", False),
                                ("monetary", False)]:
            score_col = col[0].upper() + "_score"
            try:
                rfm[score_col] = pd.qcut(
                    rfm[col], q=5,
                    labels=[5, 4, 3, 2, 1] if ascending else [1, 2, 3, 4, 5],
                    duplicates="drop"
                ).astype(int)
            except Exception:
                rfm[score_col] = 3  # 数据不足时默认中等

        rfm["RFM_score"] = rfm["R_score"] + rfm["F_score"] + rfm["M_score"]

        # 客户分层
        def segment(row):
            if row["R_score"] >= 4 and row["F_score"] >= 4:
                return "重要价值客户"
            elif row["R_score"] >= 4 and row["M_score"] >= 4:
                return "重要发展客户"
            elif row["R_score"] < 2 and row["F_score"] >= 4:
                return "重要保持客户"
            elif row["R_score"] < 2 and row["M_score"] < 2:
                return "流失客户"
            elif row["RFM_score"] >= 11:
                return "高价值客户"
            elif row["RFM_score"] >= 7:
                return "中价值客户"
            else:
                return "低价值客户"

        rfm["segment"] = rfm.apply(segment, axis=1)
        return rfm.sort_values("RFM_score", ascending=False)

    # ----------------------------------------------------------
    # 渠道分析
    # ----------------------------------------------------------

    def channel_analysis(self, start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """销售渠道效益分析"""
        df = self._filter_date(start_date, end_date)
        if "sales_channel" not in df.columns or df.empty:
            return pd.DataFrame()

        result = df.groupby("sales_channel").agg(
            total_amount=("total_amount", "sum"),
            total_profit=("profit", "sum"),
            order_count=("quantity", "count"),
            avg_profit_margin=("profit_margin", "mean"),
        ).reset_index()
        result["revenue_share"] = (
            result["total_amount"] / result["total_amount"].sum() * 100
        )
        return result.sort_values("total_amount", ascending=False)

    # ----------------------------------------------------------
    # KPI 达成分析
    # ----------------------------------------------------------

    def kpi_analysis(self, targets: Dict[str, float],
                     period: str = "current_month") -> Dict[str, Any]:
        """KPI 达成率分析"""
        df = self._get_period_data(period)

        actuals = {
            "monthly_revenue": float(df["total_amount"].sum()) if "total_amount" in df.columns else 0,
            "monthly_profit": float(df["profit"].sum()) if "profit" in df.columns else 0,
            "order_count": int(len(df)),
            "customer_count": int(df["customer_id"].nunique()) if "customer_id" in df.columns else 0,
        }

        result = {}
        for kpi, target in targets.items():
            actual = actuals.get(kpi, 0)
            achievement = (actual / target * 100) if target > 0 else 0
            result[kpi] = {
                "target": target,
                "actual": actual,
                "achievement_rate": round(achievement, 2),
                "gap": round(actual - target, 2),
                "status": "达成" if achievement >= 100 else "未达成",
            }
        return result

    # ----------------------------------------------------------
    # 综合分析摘要
    # ----------------------------------------------------------

    def generate_summary(self) -> Dict[str, Any]:
        """生成综合分析摘要"""
        if self.df is None or self.df.empty:
            return {"error": "无数据"}

        summary = {}

        # 基础统计
        summary["basic"] = {
            "total_records": len(self.df),
            "total_revenue": float(self.df.get("total_amount", pd.Series([0])).sum()),
            "total_profit": float(self.df.get("profit", pd.Series([0])).sum()),
            "avg_profit_margin": float(
                self.df["profit_margin"].mean()
                if "profit_margin" in self.df.columns else 0
            ),
        }

        # 月度趋势（最近 6 个月）
        trend = self.sales_trend(freq="M")
        if not trend.empty:
            summary["monthly_trend"] = trend.tail(6).to_dict(orient="records")

        # Top5 区域
        region = self.region_analysis()
        if not region.empty:
            summary["top_regions"] = region.head(5).to_dict(orient="records")

        # Top10 产品
        product = self.product_analysis(top_n=5)
        if not product.empty:
            summary["top_products"] = product.head(5).to_dict(orient="records")

        # 渠道分布
        channel = self.channel_analysis()
        if not channel.empty:
            summary["channels"] = channel.to_dict(orient="records")

        return summary

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    def _filter_date(self, start_date: str = None,
                     end_date: str = None) -> pd.DataFrame:
        df = self.df.copy()
        if "date" not in df.columns:
            return df
        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]
        return df

    def _get_period_data(self, period: str) -> pd.DataFrame:
        now = datetime.now()
        if period == "current_month":
            start = now.replace(day=1)
            return self._filter_date(start.strftime("%Y-%m-%d"))
        elif period == "current_quarter":
            quarter = (now.month - 1) // 3
            start = now.replace(month=quarter * 3 + 1, day=1)
            return self._filter_date(start.strftime("%Y-%m-%d"))
        elif period == "current_year":
            start = now.replace(month=1, day=1)
            return self._filter_date(start.strftime("%Y-%m-%d"))
        return self.df.copy()
