"""
生成示例营销数据（用于测试）
Generate Sample Marketing Data for Testing
"""
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


def generate_sales_data(n_records: int = 500) -> pd.DataFrame:
    """生成模拟销售数据"""
    random.seed(42)
    np.random.seed(42)

    regions = ["华东", "华北", "华南", "华中", "西南", "西北", "东北"]
    region_weights = [0.28, 0.20, 0.18, 0.12, 0.10, 0.07, 0.05]

    categories = ["电子产品", "家居用品", "服装配饰", "食品饮料", "美妆护肤"]
    products = {
        "电子产品": ["智能手机", "平板电脑", "笔记本电脑", "智能手表", "蓝牙耳机"],
        "家居用品": ["咖啡机", "扫地机器人", "空气净化器", "智能台灯", "电热毯"],
        "服装配饰": ["羽绒服", "运动鞋", "皮包", "墨镜", "围巾"],
        "食品饮料": ["有机茶叶", "进口红酒", "坚果礼盒", "咖啡豆", "蜂蜜"],
        "美妆护肤": ["面膜套装", "精华液", "防晒霜", "口红套装", "洗护套装"],
    }
    channels = ["线上商城", "线下门店", "代理商", "直销", "电商平台"]
    channel_weights = [0.35, 0.25, 0.20, 0.12, 0.08]

    salespersons = ["张伟", "李娜", "王芳", "刘洋", "陈静", "杨军", "赵明", "周慧"]
    customers = [f"客户{i:04d}" for i in range(1, 201)]
    customer_names = [f"{random.choice('赵钱孙李周吴郑王')}{random.choice('伟强华英明亮辉磊')}" for _ in customers]

    records = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 5, 16)  # 对应文件日期

    for i in range(n_records):
        # 随机日期（带季节性）
        days = (end_date - start_date).days
        day_offset = int(np.random.triangular(0, days * 0.7, days))
        date = start_date + timedelta(days=day_offset)

        # 季节性权重（Q4 销售旺季）
        if date.month in [11, 12, 1]:
            qty_multiplier = 1.5
        elif date.month in [6, 7, 8]:
            qty_multiplier = 1.2
        else:
            qty_multiplier = 1.0

        region = random.choices(regions, weights=region_weights)[0]
        category = random.choice(categories)
        product = random.choice(products[category])
        channel = random.choices(channels, weights=channel_weights)[0]
        salesperson = random.choice(salespersons)

        # 价格和数量
        base_prices = {
            "电子产品": (800, 8000), "家居用品": (200, 2000),
            "服装配饰": (100, 1500), "食品饮料": (50, 500),
            "美妆护肤": (80, 800),
        }
        price_range = base_prices[category]
        unit_price = round(random.uniform(*price_range), 2)
        quantity = max(1, int(np.random.poisson(3 * qty_multiplier)))
        total_amount = round(unit_price * quantity, 2)

        # 成本（利润率 20%-45%）
        margin_rate = random.uniform(0.20, 0.45)
        cost = round(total_amount * (1 - margin_rate), 2)
        profit = round(total_amount - cost, 2)
        profit_margin = round(profit / total_amount, 4)

        # 客户
        cust_idx = random.randint(0, len(customers) - 1)

        records.append({
            "日期": date.strftime("%Y-%m-%d"),
            "产品名称": product,
            "品类": category,
            "区域": region,
            "销售渠道": channel,
            "销售数量": quantity,
            "单价": unit_price,
            "销售金额": total_amount,
            "成本": cost,
            "利润": profit,
            "利润率": profit_margin,
            "客户ID": customers[cust_idx],
            "客户名称": customer_names[cust_idx],
            "销售人员": salesperson,
        })

    df = pd.DataFrame(records)
    df = df.sort_values("日期").reset_index(drop=True)
    return df


if __name__ == "__main__":
    print("正在生成示例营销数据...")
    df = generate_sales_data(500)

    output_path = "uploads/营销数据示例.xlsx"
    import os
    os.makedirs("uploads", exist_ok=True)
    df.to_excel(output_path, index=False)

    print(f"✅ 已生成 {len(df)} 条销售记录")
    print(f"📁 保存至: {output_path}")
    print(f"\n数据预览:")
    print(df.head(5).to_string(index=False))
    print(f"\n统计摘要:")
    print(f"  时间范围: {df['日期'].min()} ~ {df['日期'].max()}")
    print(f"  总销售额: ¥{df['销售金额'].sum():,.2f}")
    print(f"  总利润: ¥{df['利润'].sum():,.2f}")
    print(f"  平均利润率: {df['利润率'].mean()*100:.1f}%")
    print(f"  区域: {', '.join(df['区域'].unique())}")
