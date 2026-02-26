"""
Excel / CSV 数据处理模块
支持自动识别营销数据字段、清洗、标准化
Excel / CSV Data Processing Module
"""
import os
import re
import json
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
from loguru import logger


# ── 营销数据字段映射（中英文对照）────────────────────────────────────────────
FIELD_ALIASES: Dict[str, List[str]] = {
    "date":         ["日期", "时间", "date", "时间节点", "统计日期", "报告日期"],
    "sales":        ["销售额", "销售量", "营业额", "收入", "金额", "revenue", "sales", "销售金额"],
    "quantity":     ["数量", "销量", "件数", "qty", "quantity", "销售数量"],
    "product":      ["产品", "商品", "品名", "product", "商品名称", "产品名称", "货品"],
    "category":     ["分类", "品类", "类别", "category", "产品类别", "商品分类"],
    "region":       ["地区", "区域", "城市", "province", "region", "市场区域", "销售区域"],
    "channel":      ["渠道", "channel", "销售渠道", "来源", "平台"],
    "customer":     ["客户", "customer", "客户名称", "买家", "购买方"],
    "cost":         ["成本", "cost", "采购成本", "进货价"],
    "profit":       ["利润", "profit", "毛利", "净利润"],
    "profit_rate":  ["利润率", "毛利率", "profit_rate", "利润比例"],
    "salesperson":  ["销售员", "业务员", "salesperson", "负责人", "销售人员"],
    "order_id":     ["订单号", "order_id", "单号", "订单编号"],
    "status":       ["状态", "status", "订单状态", "付款状态"],
    "remark":       ["备注", "remark", "说明", "comments"],
}


def _normalize_column(col: str) -> str:
    """去除多余空格、转换为小写"""
    return str(col).strip().lower().replace(" ", "")


def _infer_column_mapping(columns: List[str]) -> Dict[str, str]:
    """自动推断列名映射：原始列名 -> 标准字段名"""
    mapping: Dict[str, str] = {}
    norm_cols = {_normalize_column(c): c for c in columns}
    for std_field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            norm_alias = _normalize_column(alias)
            if norm_alias in norm_cols:
                original_col = norm_cols[norm_alias]
                if original_col not in mapping.values():
                    mapping[original_col] = std_field
                    break
    return mapping


def _detect_encoding(file_path: str) -> str:
    import chardet
    with open(file_path, "rb") as f:
        raw = f.read(10000)
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


class ExcelProcessor:
    """
    营销 Excel/CSV 数据处理器
    功能：加载、清洗、标准化、多 Sheet 合并
    """

    def __init__(self):
        self.raw_df: Optional[pd.DataFrame] = None
        self.clean_df: Optional[pd.DataFrame] = None
        self.column_mapping: Dict[str, str] = {}
        self.metadata: Dict[str, Any] = {}

    # ── 加载文件 ───────────────────────────────────────────────────────────────
    def load_file(self, file_path: str, sheet_name=0) -> pd.DataFrame:
        path = Path(file_path)
        ext = path.suffix.lower()
        logger.info(f"加载文件: {file_path}")

        if ext in (".xlsx", ".xls", ".xlsm"):
            # 尝试读取所有 Sheet
            xl = pd.ExcelFile(file_path)
            sheet_names = xl.sheet_names
            logger.info(f"发现 Sheets: {sheet_names}")
            if sheet_name == "all":
                dfs = []
                for sn in sheet_names:
                    df = xl.parse(sn)
                    df["__sheet__"] = sn
                    dfs.append(df)
                raw = pd.concat(dfs, ignore_index=True)
            else:
                raw = xl.parse(sheet_name)
        elif ext == ".csv":
            enc = _detect_encoding(file_path)
            raw = pd.read_csv(file_path, encoding=enc)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

        self.raw_df = raw
        self.metadata = {
            "file": str(path.name),
            "rows": len(raw),
            "columns": list(raw.columns),
            "loaded_at": datetime.now().isoformat()
        }
        logger.info(f"加载完成: {len(raw)} 行 × {len(raw.columns)} 列")
        return raw

    # ── 自动识别 + 重命名列 ────────────────────────────────────────────────────
    def auto_map_columns(self) -> Dict[str, str]:
        if self.raw_df is None:
            raise RuntimeError("请先调用 load_file()")
        self.column_mapping = _infer_column_mapping(list(self.raw_df.columns))
        logger.info(f"自动列映射: {self.column_mapping}")
        return self.column_mapping

    # ── 数据清洗 ───────────────────────────────────────────────────────────────
    def clean(self) -> pd.DataFrame:
        if self.raw_df is None:
            raise RuntimeError("请先调用 load_file()")
        df = self.raw_df.copy()

        # 1. 删除全空行/列
        df.dropna(how="all", inplace=True)
        df.dropna(axis=1, how="all", inplace=True)

        # 2. 标准化列名
        mapping = self.auto_map_columns()
        df.rename(columns=mapping, inplace=True)

        # 3. 日期解析
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce", infer_datetime_format=True)
            df.sort_values("date", inplace=True)

        # 4. 数值列清洗（去除货币符号、千分位逗号）
        numeric_fields = ["sales", "quantity", "cost", "profit", "profit_rate"]
        for col in numeric_fields:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str)
                    .str.replace(r"[¥$,，\s]", "", regex=True)
                    .str.replace(r"%$", "", regex=True)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 5. 字符串列去首尾空格
        str_cols = df.select_dtypes(include="object").columns
        df[str_cols] = df[str_cols].apply(lambda x: x.str.strip() if x.dtype == object else x)

        # 6. 补全利润率
        if "profit" in df.columns and "sales" in df.columns:
            if "profit_rate" not in df.columns:
                df["profit_rate"] = df["profit"] / df["sales"].replace(0, np.nan)

        # 7. 重置索引
        df.reset_index(drop=True, inplace=True)

        self.clean_df = df
        self.metadata["clean_rows"] = len(df)
        self.metadata["clean_columns"] = list(df.columns)
        logger.info(f"清洗完成: {len(df)} 行")
        return df

    # ── 数据摘要 ───────────────────────────────────────────────────────────────
    def get_summary(self) -> Dict[str, Any]:
        df = self.clean_df
        if df is None:
            return {}
        summary: Dict[str, Any] = {
            "total_rows": len(df),
            "columns": list(df.columns),
            "date_range": None,
            "numeric_stats": {},
            "top_products": [],
            "top_regions": [],
            "top_channels": [],
            "missing_counts": df.isnull().sum().to_dict()
        }
        if "date" in df.columns:
            summary["date_range"] = {
                "start": str(df["date"].min()),
                "end": str(df["date"].max())
            }
        for col in ["sales", "quantity", "profit"]:
            if col in df.columns:
                summary["numeric_stats"][col] = {
                    "sum": round(float(df[col].sum()), 2),
                    "mean": round(float(df[col].mean()), 2),
                    "max": round(float(df[col].max()), 2),
                    "min": round(float(df[col].min()), 2),
                }
        for col, key in [("product", "top_products"), ("region", "top_regions"),
                          ("channel", "top_channels")]:
            if col in df.columns and "sales" in df.columns:
                top = (
                    df.groupby(col)["sales"].sum()
                    .sort_values(ascending=False)
                    .head(5)
                    .reset_index()
                )
                summary[key] = top.to_dict("records")
        return summary

    # ── 导出清洗后数据 ─────────────────────────────────────────────────────────
    def export(self, output_path: str, fmt: str = "xlsx") -> str:
        df = self.clean_df
        if df is None:
            raise RuntimeError("请先调用 clean()")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if fmt == "xlsx":
            df.to_excel(output_path, index=False, engine="openpyxl")
        elif fmt == "csv":
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
        elif fmt == "json":
            df.to_json(output_path, orient="records", force_ascii=False)
        logger.info(f"数据已导出: {output_path}")
        return output_path


# ── 全局处理器实例 ─────────────────────────────────────────────────────────────
processor = ExcelProcessor()
