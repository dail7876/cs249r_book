# 智能自动化业务分析系统

## 系统架构

```
business_system/
├── main.py                    # 主入口 (FastAPI)
├── config.py                  # 配置管理
├── requirements.txt           # 依赖包
├── .env.example               # 环境变量示例
├── generate_sample_data.py    # 生成测试数据
│
├── integrations/              # 数据通道接入
│   ├── wechat.py              # 企业微信
│   ├── dingtalk.py            # 钉钉
│   └── email_handler.py       # 邮件 (IMAP/SMTP)
│
├── data_processing/           # 数据处理
│   ├── processor.py           # 数据加载/清洗/标准化
│   ├── analyzer.py            # 市场分析引擎
│   └── reporter.py            # 报表生成
│
├── ai/
│   └── conversation.py        # AI 对话引擎 (Claude)
│
├── api/
│   ├── routes.py              # REST API 路由
│   └── models.py              # Pydantic 数据模型
│
├── database/
│   └── db.py                  # SQLAlchemy ORM 模型
│
└── ui/
    └── templates/
        └── index.html         # Web 对话界面
```

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY 等配置

# 3. 生成测试数据（可选）
python generate_sample_data.py

# 4. 启动服务
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 打开 Web 界面

## 功能说明

### 数据接入
| 通道 | 接入方式 | 说明 |
|------|---------|------|
| 企业微信 | Webhook | `GET/POST /api/webhook/wechat` |
| 钉钉 | 机器人 Webhook | `POST /api/webhook/dingtalk` |
| 邮件 | IMAP 轮询 | 自动检测并处理附件中的 Excel/CSV |
| 手动上传 | REST API | `POST /api/upload` |

### 市场分析功能
- **销售趋势**: 日/周/月/季/年度多粒度趋势分析
- **区域分析**: 各区域销售额、利润、市场占比
- **产品分析**: 产品销售排名、品类占比
- **RFM 客户价值**: 重要/发展/保持/流失客户分层
- **渠道分析**: 各销售渠道效益对比
- **KPI 达成**: 实际 vs 目标达成率

### AI 对话
- 自然语言查询：「本月华东区产品A的利润率是多少？」
- 多轮上下文对话
- 无 API Key 时自动降级为规则回复
- 支持微信/钉钉文字消息直接对话

### 报表
- HTML 交互式报表（含 Chart.js 图表）
- Excel 多 Sheet 报表
- 在线预览 + 下载

## API 文档

启动后访问 http://localhost:8000/docs 查看完整 Swagger 文档

## 支持的数据格式

上传文件支持以下列名（中英文均可自动识别）：

| 标准字段 | 支持的中文列名 |
|---------|-------------|
| date | 日期、时间、销售日期 |
| product_name | 产品、商品、产品名称 |
| category | 类别、品类、分类 |
| region | 区域、地区、省份 |
| sales_channel | 渠道、销售渠道 |
| quantity | 数量、销量、件数 |
| unit_price | 单价、价格 |
| total_amount | 金额、销售额、营业额 |
| cost | 成本、进价 |
| profit | 利润、毛利 |
| customer_name | 客户、客户名称 |
