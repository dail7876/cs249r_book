"""
AI 对话处理模块
AI Conversation Handler with Function Calling

支持自然语言查询营销数据、生成报表、回答业务问题
"""
import json
import uuid
from typing import Optional, Dict, List, Any, AsyncIterator
from datetime import datetime

from loguru import logger

from config import settings
from modules.analysis.market_analysis import analyzer as market_analyzer
from modules.reporting.report_generator import ReportGenerator


# ── 系统提示词 ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """你是一个智能营销数据分析助手。你可以帮助用户：
1. 查询销售数据（总销售额、订单量、利润等）
2. 分析市场趋势（月度/季度/年度趋势，同比环比）
3. 产品分析（畅销产品、ABC分析、产品排行）
4. 区域分析（各地区销售情况、市场占有率）
5. 渠道分析（各销售渠道效果对比）
6. 客户分析（RFM分析、客户价值分类）
7. 销售预测（未来销售趋势预测）
8. 生成分析报表（Excel、HTML格式）

请用简洁、专业的中文回答。当用户询问数据时，调用相应的工具函数获取数据后再回答。
如果数据不足或没有上传数据，请告知用户先上传营销数据文件。"""

# ── Function Calling 工具定义 ──────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_overall_kpi",
            "description": "获取总体KPI数据：总销售额、订单数、利润、客户数等",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "结束日期 YYYY-MM-DD"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_trend",
            "description": "获取销售趋势数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "freq": {"type": "string", "enum": ["D", "W", "ME", "QE", "YE"],
                             "description": "时间粒度：日/周/月/季/年"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_analysis",
            "description": "获取产品销售分析，包括TOP产品和ABC分析",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "显示前N名产品"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_region_analysis",
            "description": "获取区域销售分析",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_channel_analysis",
            "description": "获取销售渠道分析",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rfm_analysis",
            "description": "获取客户RFM分析（近期购买、频率、金额）",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference_date": {"type": "string", "description": "参考日期 YYYY-MM-DD"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_yoy_mom",
            "description": "获取同比（YoY）和环比（MoM）数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_period": {"type": "string", "description": "目标月份 YYYY-MM"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "获取销售预测",
            "parameters": {
                "type": "object",
                "properties": {
                    "periods": {"type": "integer", "description": "预测期数（默认3）"},
                    "freq": {"type": "string", "enum": ["D", "W", "ME", "QE"]}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_anomalies",
            "description": "检测销售数据中的异常点",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string", "description": "分析字段（sales/profit/quantity）"},
                    "std_multiplier": {"type": "number", "description": "标准差倍数阈值（默认2.0）"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "生成分析报表（Excel或HTML格式）",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["excel", "html"],
                               "description": "报表格式"},
                    "title": {"type": "string", "description": "报表标题"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"}
                },
                "required": ["format"]
            }
        }
    }
]


# ── 工具执行器 ─────────────────────────────────────────────────────────────────
class ToolExecutor:
    def __init__(self):
        self.report_gen = ReportGenerator(market_analyzer)

    async def execute(self, tool_name: str, arguments: Dict) -> Any:
        try:
            if tool_name == "get_overall_kpi":
                return market_analyzer.overall_kpi(**arguments)
            elif tool_name == "get_sales_trend":
                return market_analyzer.sales_trend(**arguments)
            elif tool_name == "get_product_analysis":
                return market_analyzer.product_analysis(**arguments)
            elif tool_name == "get_region_analysis":
                return market_analyzer.region_analysis(**arguments)
            elif tool_name == "get_channel_analysis":
                return market_analyzer.channel_analysis(**arguments)
            elif tool_name == "get_rfm_analysis":
                return market_analyzer.rfm_analysis(**arguments)
            elif tool_name == "get_yoy_mom":
                return market_analyzer.yoy_mom_comparison(**arguments)
            elif tool_name == "get_forecast":
                return market_analyzer.simple_forecast(**arguments)
            elif tool_name == "get_anomalies":
                return market_analyzer.detect_anomalies(**arguments)
            elif tool_name == "generate_report":
                fmt = arguments.pop("format", "html")
                if fmt == "excel":
                    path = self.report_gen.generate_excel_report(**arguments)
                else:
                    path = self.report_gen.generate_html_report(**arguments)
                return {"status": "success", "file_path": path,
                        "download_url": f"/api/reports/download?path={path}"}
            else:
                return {"error": f"未知工具: {tool_name}"}
        except Exception as e:
            logger.error(f"工具执行错误 [{tool_name}]: {e}")
            return {"error": str(e)}


# ── 对话管理器 ─────────────────────────────────────────────────────────────────
class DialogHandler:
    """
    多轮对话处理器
    支持 OpenAI / Anthropic 后端
    """

    def __init__(self):
        self.executor = ToolExecutor()
        self.sessions: Dict[str, List[Dict]] = {}  # session_id -> message history

    def new_session(self, session_id: Optional[str] = None) -> str:
        sid = session_id or str(uuid.uuid4())
        self.sessions[sid] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return sid

    def get_history(self, session_id: str) -> List[Dict]:
        return self.sessions.get(session_id, [])

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    async def chat(self, session_id: str, user_message: str) -> str:
        """同步式对话（等待完整回复）"""
        if session_id not in self.sessions:
            self.new_session(session_id)

        history = self.sessions[session_id]
        history.append({"role": "user", "content": user_message})

        response_text = await self._call_llm(history)
        history.append({"role": "assistant", "content": response_text})
        return response_text

    async def _call_llm(self, messages: List[Dict]) -> str:
        """调用 LLM，支持 Function Calling"""
        if settings.OPENAI_API_KEY:
            return await self._call_openai(messages)
        elif settings.ANTHROPIC_API_KEY:
            return await self._call_anthropic(messages)
        else:
            return await self._fallback_rule_based(messages[-1]["content"])

    async def _call_openai(self, messages: List[Dict]) -> str:
        """调用 OpenAI GPT（支持 Function Calling）"""
        try:
            import openai
            client = openai.AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.AI_BASE_URL
            )
            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000
            )
            msg = response.choices[0].message
            # 处理 Function Calling
            if msg.tool_calls:
                tool_messages = [msg]
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = await self.executor.execute(tc.function.name, args)
                    tool_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str)
                    })
                messages_with_tools = messages + tool_messages
                final = await client.chat.completions.create(
                    model=settings.AI_MODEL,
                    messages=messages_with_tools,
                    temperature=0.3,
                    max_tokens=2000
                )
                return final.choices[0].message.content
            return msg.content or ""
        except Exception as e:
            logger.error(f"OpenAI 调用失败: {e}")
            return f"AI 服务暂时不可用，请稍后重试。({type(e).__name__})"

    async def _call_anthropic(self, messages: List[Dict]) -> str:
        """调用 Anthropic Claude"""
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            system_msg = next(
                (m["content"] for m in messages if m["role"] == "system"),
                SYSTEM_PROMPT
            )
            non_system = [m for m in messages if m["role"] != "system"]
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=system_msg,
                messages=non_system
            )
            return response.content[0].text if response.content else ""
        except Exception as e:
            logger.error(f"Anthropic 调用失败: {e}")
            return f"AI 服务暂时不可用。({type(e).__name__})"

    async def _fallback_rule_based(self, user_message: str) -> str:
        """规则基础回退（无 LLM Key 时）"""
        msg = user_message.lower()
        if any(k in msg for k in ["kpi", "总览", "概况", "总销售", "摘要"]):
            try:
                kpi = market_analyzer.overall_kpi()
                lines = [f"**营销数据总览**"]
                for k, v in kpi.items():
                    lines.append(f"• {k}: {v:,.2f}" if isinstance(v, float) else f"• {k}: {v}")
                return "\n".join(lines)
            except Exception as e:
                return f"暂无数据或数据加载失败: {e}"
        elif any(k in msg for k in ["趋势", "走势", "月度", "trend"]):
            try:
                trend = market_analyzer.sales_trend("ME")
                if not trend:
                    return "暂无趋势数据，请先上传数据文件。"
                lines = ["**月度销售趋势**"]
                for t in trend[-6:]:
                    mom = f"({t['mom_pct']:+.1f}%)" if t.get("mom_pct") else ""
                    lines.append(f"• {t['period']}: ¥{t['sales']:,.2f} {mom}")
                return "\n".join(lines)
            except Exception as e:
                return f"趋势分析失败: {e}"
        elif any(k in msg for k in ["产品", "商品", "product"]):
            try:
                prod = market_analyzer.product_analysis(5)
                tops = prod.get("top_by_sales", [])
                if not tops:
                    return "暂无产品数据。"
                lines = ["**产品销售 Top 5**"]
                for i, p in enumerate(tops[:5], 1):
                    lines.append(f"{i}. {p.get('product', '')}: ¥{p.get('sales', 0):,.2f}")
                return "\n".join(lines)
            except Exception as e:
                return f"产品分析失败: {e}"
        elif any(k in msg for k in ["报表", "报告", "生成", "excel", "html"]):
            fmt = "excel" if "excel" in msg else "html"
            try:
                rg = ReportGenerator(market_analyzer)
                if fmt == "excel":
                    path = rg.generate_excel_report()
                else:
                    path = rg.generate_html_report()
                return f"✅ 报表已生成！\n下载链接: /api/reports/download?path={path}"
            except Exception as e:
                return f"报表生成失败: {e}"
        elif any(k in msg for k in ["帮助", "help", "功能", "命令"]):
            return """**我能帮您做什么？**

📊 **数据查询**
• 查看总销售额、利润、订单量等KPI
• 月度/季度/年度销售趋势
• 同比、环比分析

🛍️ **产品分析**
• 畅销产品排行
• ABC产品分类分析

🗺️ **区域 & 渠道**
• 各地区销售占比
• 渠道效果对比

👥 **客户分析**
• RFM客户价值分类
• 客户购买行为分析

📈 **预测与预警**
• 未来销售预测
• 异常数据检测

📋 **报表生成**
• 生成Excel多维报表
• 生成HTML可视化报表

💡 直接用自然语言提问，例如：
- "本月销售额是多少？"
- "生成一份Excel报表"
- "哪个产品销售最好？"
"""
        else:
            return ("您好！我是营销数据分析助手。\n"
                    "请提问，例如：「显示本月销售KPI」「生成报表」「分析产品销售」\n"
                    "或输入「帮助」查看所有功能。")


# ── 全局对话处理器 ─────────────────────────────────────────────────────────────
dialog_handler = DialogHandler()
