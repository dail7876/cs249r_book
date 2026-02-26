"""
市场分析引擎
Market Analysis Engine

功能：销售趋势分析、产品分析、区域分析、渠道分析、
      客户分析、同比/环比、预测、异常检测
"""
import warnings
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore")


# ── 工具函数 ───────────────────────────────────────────────────────────────────
def _safe_pct(a: float, b: float) -> Optional[float]:
    """安全计算同比/环比百分比"""
    if b is None or b == 0:
        return None
    return round((a - b) / abs(b) * 100, 2)


def _rank_df(df: pd.DataFrame, value_col: str, n: int = 10) -> pd.DataFrame:
    return df.nlargest(n, value_col).reset_index(drop=True)


class MarketAnalyzer:
    """
    核心市场分析器
    输入：已清洗的 DataFrame
    """

    def __init__(self, df: Optional[pd.DataFrame] = None):
        self.df = df

    def set_data(self, df: pd.DataFrame):
        self.df = df

    def _require_df(self):
        if self.df is None or self.df.empty:
            raise RuntimeError("尚未加载数据，请先上传并处理数据文件")

    # ─────────────────────────────────────────────────────────────────────────
    # 1. 总览 KPI
    # ─────────────────────────────────────────────────────────────────────────
    def overall_kpi(self, date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> Dict[str, Any]:
        self._require_df()
        df = self._filter_date(date_from, date_to)

        kpi: Dict[str, Any] = {}
        if "sales" in df.columns:
            kpi["total_sales"] = round(float(df["sales"].sum()), 2)
            kpi["avg_order_value"] = round(float(df["sales"].mean()), 2)
            kpi["order_count"] = len(df)
        if "quantity" in df.columns:
            kpi["total_quantity"] = round(float(df["quantity"].sum()), 2)
        if "profit" in df.columns:
            kpi["total_profit"] = round(float(df["profit"].sum()), 2)
        if "profit_rate" in df.columns:
            kpi["avg_profit_rate"] = round(float(df["profit_rate"].mean() * 100), 2)
        if "customer" in df.columns:
            kpi["unique_customers"] = int(df["customer"].nunique())
        if "product" in df.columns:
            kpi["unique_products"] = int(df["product"].nunique())
        return kpi

    # ─────────────────────────────────────────────────────────────────────────
    # 2. 时间趋势分析
    # ─────────────────────────────────────────────────────────────────────────
    def sales_trend(self, freq: str = "ME", date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> List[Dict]:
        """
        freq: 'D' 日 | 'W' 周 | 'ME' 月 | 'QE' 季 | 'YE' 年
        """
        self._require_df()
        df = self._filter_date(date_from, date_to)
        if "date" not in df.columns or "sales" not in df.columns:
            return []
        ts = df.set_index("date")["sales"].resample(freq).sum()
        result = []
        prev = None
        for dt, val in ts.items():
            item = {
                "period": str(dt.date()),
                "sales": round(float(val), 2),
                "mom_pct": _safe_pct(val, prev)
            }
            result.append(item)
            prev = val
        return result

    def multi_metric_trend(self, metrics: List[str] = None,
                            freq: str = "ME") -> Dict[str, List]:
        self._require_df()
        metrics = metrics or ["sales", "profit", "quantity"]
        df = self._filter_date()
        if "date" not in df.columns:
            return {}
        result: Dict[str, List] = {}
        for m in metrics:
            if m not in df.columns:
                continue
            ts = df.set_index("date")[m].resample(freq).sum()
            result[m] = [
                {"period": str(dt.date()), "value": round(float(v), 2)}
                for dt, v in ts.items()
            ]
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # 3. 产品分析
    # ─────────────────────────────────────────────────────────────────────────
    def product_analysis(self, top_n: int = 10,
                          date_from: Optional[str] = None,
                          date_to: Optional[str] = None) -> Dict[str, Any]:
        self._require_df()
        df = self._filter_date(date_from, date_to)
        if "product" not in df.columns:
            return {}
        agg: Dict[str, Any] = {}
        for col in ["sales", "quantity", "profit"]:
            if col not in df.columns:
                continue
        grp = df.groupby("product").agg(
            sales=("sales", "sum") if "sales" in df.columns else ("product", "count"),
            quantity=("quantity", "sum") if "quantity" in df.columns else ("product", "count"),
            profit=("profit", "sum") if "profit" in df.columns else ("product", "count"),
            orders=("product", "count")
        ).reset_index()

        top_by_sales = _rank_df(grp, "sales", top_n).to_dict("records")
        top_by_qty = _rank_df(grp, "quantity", top_n).to_dict("records")

        # ABC 分析
        grp_sorted = grp.sort_values("sales", ascending=False)
        total = grp_sorted["sales"].sum()
        grp_sorted["cum_pct"] = grp_sorted["sales"].cumsum() / total * 100
        grp_sorted["abc"] = pd.cut(
            grp_sorted["cum_pct"],
            bins=[0, 70, 90, 100],
            labels=["A", "B", "C"]
        )
        abc_counts = grp_sorted["abc"].value_counts().to_dict()

        return {
            "top_by_sales": top_by_sales,
            "top_by_quantity": top_by_qty,
            "abc_analysis": {
                "A": int(abc_counts.get("A", 0)),
                "B": int(abc_counts.get("B", 0)),
                "C": int(abc_counts.get("C", 0))
            },
            "total_products": int(grp["product"].nunique())
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 4. 区域分析
    # ─────────────────────────────────────────────────────────────────────────
    def region_analysis(self, top_n: int = 10,
                         date_from: Optional[str] = None,
                         date_to: Optional[str] = None) -> List[Dict]:
        self._require_df()
        df = self._filter_date(date_from, date_to)
        if "region" not in df.columns or "sales" not in df.columns:
            return []
        grp = (
            df.groupby("region")
            .agg(
                sales=("sales", "sum"),
                orders=("region", "count"),
                profit=("profit", "sum") if "profit" in df.columns else ("region", "count")
            )
            .reset_index()
        )
        total_sales = grp["sales"].sum()
        grp["sales_share_pct"] = (grp["sales"] / total_sales * 100).round(2)
        return _rank_df(grp, "sales", top_n).to_dict("records")

    # ─────────────────────────────────────────────────────────────────────────
    # 5. 渠道分析
    # ─────────────────────────────────────────────────────────────────────────
    def channel_analysis(self, date_from: Optional[str] = None,
                          date_to: Optional[str] = None) -> List[Dict]:
        self._require_df()
        df = self._filter_date(date_from, date_to)
        if "channel" not in df.columns or "sales" not in df.columns:
            return []
        grp = (
            df.groupby("channel")
            .agg(
                sales=("sales", "sum"),
                orders=("channel", "count"),
                profit=("profit", "sum") if "profit" in df.columns else ("channel", "count")
            )
            .reset_index()
        )
        total = grp["sales"].sum()
        grp["share_pct"] = (grp["sales"] / total * 100).round(2)
        return grp.sort_values("sales", ascending=False).to_dict("records")

    # ─────────────────────────────────────────────────────────────────────────
    # 6. 客户分析 (RFM)
    # ─────────────────────────────────────────────────────────────────────────
    def rfm_analysis(self, reference_date: Optional[str] = None) -> List[Dict]:
        self._require_df()
        df = self.df.copy()
        required = {"customer", "date", "sales"}
        if not required.issubset(df.columns):
            return []
        ref = pd.Timestamp(reference_date) if reference_date else df["date"].max()
        rfm = df.groupby("customer").agg(
            recency=("date", lambda x: (ref - x.max()).days),
            frequency=("date", "count"),
            monetary=("sales", "sum")
        ).reset_index()

        for col in ["recency", "frequency", "monetary"]:
            try:
                rfm[f"{col}_score"] = pd.qcut(
                    rfm[col], 4,
                    labels=[4, 3, 2, 1] if col == "recency" else [1, 2, 3, 4],
                    duplicates="drop"
                ).astype(int)
            except Exception:
                rfm[f"{col}_score"] = 2

        rfm["rfm_score"] = (
            rfm["recency_score"].astype(str)
            + rfm["frequency_score"].astype(str)
            + rfm["monetary_score"].astype(str)
        )

        def segment(row):
            r, f, m = row["recency_score"], row["frequency_score"], row["monetary_score"]
            if r >= 3 and f >= 3 and m >= 3:
                return "重要价值客户"
            elif r >= 3 and f < 3 and m >= 3:
                return "重要发展客户"
            elif r < 3 and f >= 3 and m >= 3:
                return "重要保持客户"
            elif r < 3 and f < 3 and m >= 3:
                return "重要挽留客户"
            elif r >= 3 and f >= 3:
                return "一般价值客户"
            elif r >= 3:
                return "新客户"
            else:
                return "流失风险客户"

        rfm["segment"] = rfm.apply(segment, axis=1)
        rfm["monetary"] = rfm["monetary"].round(2)
        return rfm.sort_values("monetary", ascending=False).head(50).to_dict("records")

    # ─────────────────────────────────────────────────────────────────────────
    # 7. 同比 / 环比
    # ─────────────────────────────────────────────────────────────────────────
    def yoy_mom_comparison(self, target_period: Optional[str] = None) -> Dict[str, Any]:
        """
        同比（Year-over-Year）和环比（Month-over-Month）分析
        target_period: 'YYYY-MM' 格式，默认最近一个月
        """
        self._require_df()
        df = self.df.copy()
        if "date" not in df.columns or "sales" not in df.columns:
            return {}
        df["year_month"] = df["date"].dt.to_period("M")
        monthly = df.groupby("year_month")["sales"].sum()
        if target_period:
            target = pd.Period(target_period, "M")
        else:
            target = monthly.index.max()
        prev_month = target - 1
        prev_year = target - 12
        current_val = float(monthly.get(target, 0))
        mom_val = float(monthly.get(prev_month, 0))
        yoy_val = float(monthly.get(prev_year, 0))
        return {
            "period": str(target),
            "current_sales": round(current_val, 2),
            "mom_sales": round(mom_val, 2),
            "yoy_sales": round(yoy_val, 2),
            "mom_pct": _safe_pct(current_val, mom_val),
            "yoy_pct": _safe_pct(current_val, yoy_val),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 8. 简单销售预测
    # ─────────────────────────────────────────────────────────────────────────
    def simple_forecast(self, periods: int = 3, freq: str = "ME") -> List[Dict]:
        """基于线性回归 + 移动平均的简单预测"""
        self._require_df()
        df = self._filter_date()
        if "date" not in df.columns or "sales" not in df.columns:
            return []
        ts = df.set_index("date")["sales"].resample(freq).sum()
        if len(ts) < 3:
            return []
        x = np.arange(len(ts))
        y = ts.values
        # 线性趋势
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs
        # 移动平均
        window = min(3, len(ts))
        ma = float(ts.rolling(window).mean().iloc[-1])
        result = []
        last_dt = ts.index[-1]
        for i in range(1, periods + 1):
            trend_val = slope * (len(ts) + i - 1) + intercept
            blended = 0.6 * trend_val + 0.4 * ma
            next_period = last_dt + i * pd.tseries.frequencies.to_offset(freq)
            result.append({
                "period": str(next_period.date()) if hasattr(next_period, "date") else str(next_period),
                "forecast_sales": round(max(0, float(blended)), 2),
                "trend_sales": round(max(0, float(trend_val)), 2)
            })
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # 9. 异常检测
    # ─────────────────────────────────────────────────────────────────────────
    def detect_anomalies(self, column: str = "sales",
                          std_multiplier: float = 2.0) -> List[Dict]:
        self._require_df()
        df = self._filter_date()
        if column not in df.columns or "date" not in df.columns:
            return []
        ts = df.set_index("date")[column].resample("D").sum()
        mean = ts.mean()
        std = ts.std()
        anomalies = ts[abs(ts - mean) > std_multiplier * std]
        return [
            {
                "date": str(dt.date()),
                "value": round(float(val), 2),
                "mean": round(float(mean), 2),
                "deviation": round(float(abs(val - mean) / std), 2)
            }
            for dt, val in anomalies.items()
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # 10. 品类交叉分析
    # ─────────────────────────────────────────────────────────────────────────
    def category_region_matrix(self) -> Dict[str, Any]:
        self._require_df()
        df = self._filter_date()
        if not {"category", "region", "sales"}.issubset(df.columns):
            return {}
        pivot = pd.pivot_table(
            df, values="sales",
            index="category", columns="region",
            aggfunc="sum", fill_value=0
        )
        return {
            "matrix": pivot.round(2).to_dict(),
            "categories": list(pivot.index),
            "regions": list(pivot.columns)
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 工具
    # ─────────────────────────────────────────────────────────────────────────
    def _filter_date(self, date_from: Optional[str] = None,
                     date_to: Optional[str] = None) -> pd.DataFrame:
        df = self.df.copy()
        if "date" in df.columns:
            if date_from:
                df = df[df["date"] >= pd.Timestamp(date_from)]
            if date_to:
                df = df[df["date"] <= pd.Timestamp(date_to)]
        return df


# ── 全局分析器实例 ─────────────────────────────────────────────────────────────
analyzer = MarketAnalyzer()
