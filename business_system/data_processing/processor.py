"""
数据处理引擎
Data Processing Engine

支持功能:
- Excel/CSV 文件解析
- 数据清洗和标准化
- 自动识别销售数据字段
- 批量导入数据库
"""
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 字段映射：自动识别常见的列名
FIELD_ALIASES = {
    "date": ["日期", "时间", "date", "销售日期", "交易日期", "订单日期", "创建时间"],
    "product_name": ["产品", "商品", "产品名称", "商品名称", "product", "item", "货品"],
    "category": ["类别", "品类", "分类", "category", "产品类别", "商品分类"],
    "region": ["区域", "地区", "region", "省份", "城市", "销售区域"],
    "sales_channel": ["渠道", "销售渠道", "channel", "来源", "销售来源"],
    "quantity": ["数量", "销量", "qty", "quantity", "件数", "销售数量"],
    "unit_price": ["单价", "价格", "unit_price", "price", "售价"],
    "total_amount": ["金额", "销售额", "revenue", "amount", "总金额", "销售金额", "营业额"],
    "cost": ["成本", "cost", "进价", "采购成本"],
    "profit": ["利润", "profit", "毛利", "净利润"],
    "profit_margin": ["利润率", "毛利率", "profit_margin", "利润比率"],
    "customer_id": ["客户ID", "客户编号", "customer_id", "客户代码"],
    "customer_name": ["客户", "客户名称", "customer", "买家", "客户姓名"],
    "salesperson": ["销售人员", "业务员", "salesperson", "销售员", "经办人"],
}


class DataProcessor:
    """数据处理引擎"""

    def __init__(self, db_session=None):
        self.db = db_session

    def load_file(self, filepath: str) -> Optional[pd.DataFrame]:
        """加载数据文件（Excel/CSV）"""
        path = Path(filepath)
        if not path.exists():
            logger.error(f"文件不存在: {filepath}")
            return None

        try:
            if path.suffix in (".xlsx", ".xls"):
                # 尝试读取所有 Sheet
                xl = pd.ExcelFile(filepath)
                sheets = xl.sheet_names
                logger.info(f"Excel 文件包含 Sheet: {sheets}")

                if len(sheets) == 1:
                    df = pd.read_excel(filepath, sheet_name=sheets[0])
                else:
                    # 合并所有 Sheet 或选取最大的 Sheet
                    dfs = []
                    for sheet in sheets:
                        try:
                            df_s = pd.read_excel(filepath, sheet_name=sheet)
                            if not df_s.empty:
                                df_s["_sheet"] = sheet
                                dfs.append(df_s)
                        except Exception:
                            pass
                    if dfs:
                        df = pd.concat(dfs, ignore_index=True)
                    else:
                        return None

            elif path.suffix == ".csv":
                # 自动检测编码
                for enc in ["utf-8", "gbk", "gb2312", "utf-8-sig"]:
                    try:
                        df = pd.read_csv(filepath, encoding=enc)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    return None

            elif path.suffix == ".json":
                df = pd.read_json(filepath)
            else:
                logger.error(f"不支持的文件格式: {path.suffix}")
                return None

            logger.info(f"成功加载文件: {path.name}, 行数: {len(df)}, 列数: {len(df.columns)}")
            return df

        except Exception as e:
            logger.error(f"加载文件失败 {filepath}: {e}")
            return None

    def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名，自动映射已知字段"""
        df = df.copy()
        col_mapping = {}

        for col in df.columns:
            col_lower = str(col).strip().lower()
            for standard_name, aliases in FIELD_ALIASES.items():
                if col_lower in [a.lower() for a in aliases] or col_lower == standard_name:
                    col_mapping[col] = standard_name
                    break

        if col_mapping:
            df.rename(columns=col_mapping, inplace=True)
            logger.info(f"列名映射: {col_mapping}")

        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        df = df.copy()

        # 去除完全空行
        df.dropna(how="all", inplace=True)

        # 清理字符串列
        str_cols = df.select_dtypes(include="object").columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({"nan": None, "NaN": None, "": None})

        # 处理日期列
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            invalid_dates = df["date"].isna().sum()
            if invalid_dates > 0:
                logger.warning(f"无效日期行数: {invalid_dates}，将使用当前日期填充")
                df["date"].fillna(datetime.now(), inplace=True)

        # 处理数值列
        numeric_cols = ["quantity", "unit_price", "total_amount", "cost",
                        "profit", "profit_margin"]
        for col in numeric_cols:
            if col in df.columns:
                # 移除货币符号和千分位
                if df[col].dtype == object:
                    df[col] = (
                        df[col].astype(str)
                        .str.replace(r"[¥,$,，,\s]", "", regex=True)
                        .str.replace(",", "")
                    )
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # 自动计算缺失字段
        if "total_amount" not in df.columns and "quantity" in df.columns and "unit_price" in df.columns:
            df["total_amount"] = df["quantity"] * df["unit_price"]

        if "profit" not in df.columns and "total_amount" in df.columns and "cost" in df.columns:
            df["profit"] = df["total_amount"] - df["cost"]

        if "profit_margin" not in df.columns and "total_amount" in df.columns:
            df["profit_margin"] = np.where(
                df["total_amount"] > 0,
                df["profit"] / df["total_amount"],
                0.0
            )

        logger.info(f"数据清洗完成，有效行数: {len(df)}")
        return df

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """完整处理流程"""
        df = self.normalize_columns(df)
        df = self.clean_data(df)
        return df

    def process_file(self, filepath: str) -> Optional[pd.DataFrame]:
        """从文件加载并处理数据"""
        df = self.load_file(filepath)
        if df is None:
            return None
        return self.process_dataframe(df)

    def to_sales_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """将 DataFrame 转换为销售记录字典列表"""
        records = []
        for _, row in df.iterrows():
            record = {
                "date": row.get("date", datetime.now()),
                "product_name": row.get("product_name") or "未知产品",
                "category": row.get("category") or "其他",
                "region": row.get("region") or "未知区域",
                "sales_channel": row.get("sales_channel") or "未知渠道",
                "quantity": int(row.get("quantity", 0)),
                "unit_price": float(row.get("unit_price", 0)),
                "total_amount": float(row.get("total_amount", 0)),
                "cost": float(row.get("cost", 0)),
                "profit": float(row.get("profit", 0)),
                "profit_margin": float(row.get("profit_margin", 0)),
                "customer_id": row.get("customer_id"),
                "customer_name": row.get("customer_name"),
                "salesperson": row.get("salesperson"),
            }
            records.append(record)
        return records

    def get_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """获取数据摘要"""
        summary = {
            "total_rows": len(df),
            "columns": list(df.columns),
            "date_range": None,
            "total_amount": 0.0,
            "total_profit": 0.0,
            "avg_profit_margin": 0.0,
            "regions": [],
            "categories": [],
            "channels": [],
        }

        if "date" in df.columns:
            min_date = df["date"].min()
            max_date = df["date"].max()
            if pd.notna(min_date) and pd.notna(max_date):
                summary["date_range"] = {
                    "start": min_date.strftime("%Y-%m-%d"),
                    "end": max_date.strftime("%Y-%m-%d"),
                }

        if "total_amount" in df.columns:
            summary["total_amount"] = float(df["total_amount"].sum())
        if "profit" in df.columns:
            summary["total_profit"] = float(df["profit"].sum())
        if "profit_margin" in df.columns:
            valid = df["profit_margin"].replace([np.inf, -np.inf], np.nan).dropna()
            summary["avg_profit_margin"] = float(valid.mean()) if len(valid) > 0 else 0.0

        for col, key in [("region", "regions"), ("category", "categories"),
                         ("sales_channel", "channels")]:
            if col in df.columns:
                summary[key] = df[col].dropna().unique().tolist()[:20]

        return summary
