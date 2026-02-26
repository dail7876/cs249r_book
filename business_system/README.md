# 智能营销业务系统

> 自动接收微信/钉钉/邮件数据 · AI 对话查询 · 市场分析 · 报表生成

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    数据接入层                            │
│  微信企业号 Webhook  │  钉钉机器人  │  邮件 IMAP 轮询   │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                   数据处理层                             │
│  Excel/CSV 解析  │  字段自动识别  │  数据清洗标准化      │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                   分析引擎层                             │
│  KPI总览 │ 趋势分析 │ 产品/区域/渠道 │ RFM │ 预测/异常  │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                   交互层                                 │
│    AI 对话（GPT/Claude）  │  Web 看板  │  报表生成       │
└─────────────────────────────────────────────────────────┘
```

## 功能列表

### 📥 数据接入
| 渠道 | 说明 |
|------|------|
| Web 上传 | 拖拽上传 Excel / CSV 文件 |
| 微信企业号 | 自动接收用户发送的数据文件或查询消息 |
| 钉钉机器人 | 通过自定义机器人接收消息和数据文件 |
| 邮件 IMAP | 自动轮询邮箱，提取附件数据文件 |

### 📊 市场分析功能
- **KPI 总览**：总销售额、利润、订单数、客户数等核心指标
- **销售趋势**：日/周/月/季/年度趋势，支持多指标对比
- **同比/环比**：自动计算 YoY / MoM 变化
- **产品分析**：TOP 产品排行、ABC 产品分类
- **区域分析**：各地区销售占比、市场份额
- **渠道分析**：各销售渠道效果对比
- **客户 RFM**：近期性-频率-金额三维客户分类
- **销售预测**：基于历史趋势的未来销售预测
- **异常检测**：自动识别销售数据中的异常点
- **品类区域矩阵**：多维度交叉分析

### 💬 AI 智能对话
- 自然语言查询数据（"本月销售额是多少？"）
- 支持 OpenAI GPT 和 Anthropic Claude
- Function Calling 自动调用分析函数
- 多轮对话上下文保持
- 无 API Key 时启用规则引擎兜底

### 📋 报表生成
- **Excel 多维报表**：含 KPI/趋势/产品/区域/渠道/RFM/预测等 Sheet
- **HTML 可视化报表**：Plotly 交互式图表
- 历史报表管理与下载

---

## 快速启动

### 1. 安装依赖
```bash
cd business_system
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 填入实际配置
```

### 3. 启动服务
```bash
python main.py
```

访问 http://localhost:8000

### API 文档
访问 http://localhost:8000/docs

---

## Webhook 配置

### 微信企业号
1. 在企业微信后台创建自建应用
2. 设置接收消息 URL：`https://your-domain.com/webhook/wechat`
3. 填写 Token 和 EncodingAESKey

### 钉钉机器人
1. 在钉钉群创建自定义机器人
2. 设置 Webhook URL：`https://your-domain.com/webhook/dingtalk`
3. 配置加签密钥

### 邮件轮询
1. 开启邮箱 IMAP 访问权限
2. 在 .env 中填写邮箱账号和授权码
3. 系统自动每 5 分钟检查新邮件

---

## API 接口

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/upload` | POST | 上传数据文件 |
| `/api/analysis/kpi` | GET | KPI 数据 |
| `/api/analysis/trend` | GET | 销售趋势 |
| `/api/analysis/products` | GET | 产品分析 |
| `/api/analysis/regions` | GET | 区域分析 |
| `/api/analysis/channels` | GET | 渠道分析 |
| `/api/analysis/rfm` | GET | 客户 RFM |
| `/api/analysis/yoy-mom` | GET | 同比环比 |
| `/api/analysis/forecast` | GET | 销售预测 |
| `/api/analysis/anomalies` | GET | 异常检测 |
| `/api/reports/generate` | POST | 生成报表 |
| `/api/reports/download/{file}` | GET | 下载报表 |
| `/api/chat` | POST | AI 对话（REST） |
| `/ws/chat/{session_id}` | WS | AI 对话（WebSocket） |
| `/webhook/wechat` | GET/POST | 微信消息接收 |
| `/webhook/dingtalk` | POST | 钉钉消息接收 |

---

## 目录结构

```
business_system/
├── main.py                      # 启动入口
├── config.py                    # 配置管理
├── requirements.txt             # 依赖清单
├── .env.example                 # 环境变量模板
├── modules/
│   ├── ingestion/
│   │   ├── wechat.py            # 微信接入
│   │   ├── dingtalk.py          # 钉钉接入
│   │   └── email_handler.py     # 邮件接入
│   ├── processing/
│   │   ├── excel_processor.py   # Excel 处理
│   │   └── database.py          # 数据持久化
│   ├── analysis/
│   │   └── market_analysis.py   # 市场分析引擎
│   ├── reporting/
│   │   └── report_generator.py  # 报表生成
│   └── chat/
│       └── dialog_handler.py    # AI 对话处理
├── web/
│   ├── app.py                   # FastAPI 主应用
│   ├── templates/
│   │   └── index.html           # 前端主页
│   └── static/
│       ├── css/main.css         # 样式
│       └── js/main.js           # 前端逻辑
└── data/
    ├── uploads/                 # 上传文件
    └── reports/                 # 生成报表
```
