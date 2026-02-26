"""
AI 对话引擎
AI Conversation Engine

基于 Claude API 的智能对话，支持:
- 自然语言查询数据
- 上下文感知的多轮对话
- 意图识别与路由
- 结构化回复生成
"""
import json
import logging
import re
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的业务数据分析助手，服务于企业的市场分析和销售管理。

你的核心能力:
1. **数据查询**: 理解用户的自然语言查询，转换为具体的数据查询操作
2. **市场分析**: 提供销售趋势、区域对比、产品分析、客户价值等分析
3. **报表生成**: 根据用户需求生成相应的业务报表
4. **业务洞察**: 基于数据提供有价值的业务洞察和建议

可用的数据分析功能:
- sales_trend: 销售趋势（参数: freq=M/D/W/Q/Y, start_date, end_date）
- region_analysis: 区域销售分析
- product_analysis: 产品/品类分析（参数: top_n）
- rfm_analysis: RFM 客户价值分析
- channel_analysis: 渠道效益分析
- kpi_analysis: KPI 达成分析
- generate_report: 生成完整报表（参数: format=html/excel）

当用户提问时，请:
1. 理解用户意图
2. 如需调用数据分析，返回 JSON 格式的函数调用指令
3. 以清晰、专业的中文回复
4. 用数据支持你的分析观点

如果需要调用分析函数，请在回复中包含如下格式的 JSON 块:
```json
{"action": "function_name", "params": {...}}
```

始终保持专业、简洁、有洞察力的回答风格。"""

# 意图关键词映射
INTENT_PATTERNS = {
    "sales_trend": [
        r"(销售|营收|收入).*(趋势|变化|走势|增长)",
        r"(月度|季度|年度|周).*(销售|数据)",
        r"(增长|下降|对比).*(情况|分析)",
        r"trend|monthly|quarterly",
    ],
    "region_analysis": [
        r"(区域|地区|省|市).*(销售|数据|对比|分析)",
        r"(华东|华北|华南|华中|西南|西北|东北)",
        r"region|area|location",
    ],
    "product_analysis": [
        r"(产品|商品|品类|SKU).*(销售|数据|排名|分析)",
        r"(最热|畅销|TOP|最高).*(产品|商品)",
        r"product|item|category",
    ],
    "rfm_analysis": [
        r"(客户|买家).*(价值|分层|分析|RFM)",
        r"(重要|高价值|流失).*(客户|用户)",
        r"rfm|customer.*(value|segment)",
    ],
    "channel_analysis": [
        r"(渠道|来源|线上|线下|直销|代理).*(分析|对比|效益)",
        r"channel|source",
    ],
    "kpi_analysis": [
        r"(KPI|指标|目标|达成|完成).*(分析|情况|率)",
        r"kpi|target|achievement",
    ],
    "generate_report": [
        r"(生成|创建|制作|出).*(报表|报告|分析报告)",
        r"report|summary",
    ],
    "query_data": [
        r"查询|查看|看看|告诉我",
        r"(本月|上月|今年|去年).*(数据|情况)",
        r"query|show|tell me",
    ],
}


class ConversationEngine:
    """AI 对话引擎"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6",
                 max_tokens: int = 4096, analyzer=None, reporter=None):
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.model = model
        self.max_tokens = max_tokens
        self.analyzer = analyzer
        self.reporter = reporter
        self._sessions: Dict[str, List[Dict]] = {}

    def get_or_create_session(self, session_id: str = None) -> str:
        """获取或创建对话会话"""
        if session_id is None or session_id not in self._sessions:
            session_id = session_id or str(uuid.uuid4())
            self._sessions[session_id] = []
        return session_id

    def detect_intent(self, text: str) -> str:
        """检测用户意图"""
        text_lower = text.lower()
        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        return "general"

    async def chat(self, user_message: str,
                   session_id: str = None) -> Dict[str, Any]:
        """处理一轮对话，返回回复和可能的数据操作"""
        session_id = self.get_or_create_session(session_id)
        history = self._sessions[session_id]

        # 添加用户消息
        history.append({"role": "user", "content": user_message})

        # 检测意图（快速路径：无 API Key 时用规则）
        intent = self.detect_intent(user_message)
        data_result = None

        # 先尝试执行数据操作
        if self.analyzer and intent != "general":
            data_result = await self._execute_data_action(intent, user_message)

        # 调用 AI 生成回复
        ai_reply = await self._generate_reply(
            history, data_result, intent, user_message
        )

        # 保存助手回复到历史
        history.append({"role": "assistant", "content": ai_reply})

        # 限制历史长度（保留最近 20 轮）
        if len(history) > 40:
            self._sessions[session_id] = history[-40:]

        return {
            "session_id": session_id,
            "reply": ai_reply,
            "intent": intent,
            "data_result": data_result,
            "timestamp": datetime.now().isoformat(),
        }

    async def _execute_data_action(self, intent: str,
                                    user_message: str) -> Optional[Dict]:
        """根据意图执行数据操作"""
        try:
            if intent == "sales_trend" and self.analyzer:
                df = self.analyzer.sales_trend(freq="M")
                if not df.empty:
                    return {
                        "type": "sales_trend",
                        "data": df.tail(6).to_dict(orient="records"),
                        "summary": f"最近 {len(df)} 个月销售趋势数据",
                    }

            elif intent == "region_analysis" and self.analyzer:
                df = self.analyzer.region_analysis()
                if not df.empty:
                    return {
                        "type": "region_analysis",
                        "data": df.head(10).to_dict(orient="records"),
                        "summary": f"共 {len(df)} 个区域数据",
                    }

            elif intent == "product_analysis" and self.analyzer:
                df = self.analyzer.product_analysis(top_n=10)
                if not df.empty:
                    return {
                        "type": "product_analysis",
                        "data": df.head(10).to_dict(orient="records"),
                        "summary": f"TOP {len(df)} 产品数据",
                    }

            elif intent == "rfm_analysis" and self.analyzer:
                df = self.analyzer.rfm_analysis()
                if not df.empty:
                    segment_counts = df["segment"].value_counts().to_dict()
                    return {
                        "type": "rfm_analysis",
                        "data": segment_counts,
                        "summary": f"共 {len(df)} 个客户完成 RFM 分析",
                    }

            elif intent == "channel_analysis" and self.analyzer:
                df = self.analyzer.channel_analysis()
                if not df.empty:
                    return {
                        "type": "channel_analysis",
                        "data": df.to_dict(orient="records"),
                        "summary": f"共 {len(df)} 个渠道数据",
                    }

            elif intent == "generate_report" and self.analyzer and self.reporter:
                summary = self.analyzer.generate_summary()
                report_path = self.reporter.generate_html_report(
                    "业务综合分析报告", summary
                )
                return {
                    "type": "report_generated",
                    "report_path": report_path,
                    "summary": summary,
                }

        except Exception as e:
            logger.error(f"数据操作执行失败: {e}")

        return None

    async def _generate_reply(self, history: List[Dict],
                               data_result: Optional[Dict],
                               intent: str,
                               user_message: str) -> str:
        """生成 AI 回复"""
        # 无 API Key 时使用规则回复
        if self.client is None:
            return self._rule_based_reply(user_message, intent, data_result)

        # 构造带数据结果的消息
        messages = history[:-1]  # 不含最后一条用户消息
        if data_result:
            data_context = (
                f"\n\n[系统已获取到相关数据]\n"
                f"{json.dumps(data_result, ensure_ascii=False, indent=2)}\n"
                f"请基于以上数据回答用户问题。"
            )
            messages = messages + [{
                "role": "user",
                "content": user_message + data_context
            }]
        else:
            messages = history

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"AI API 调用失败: {e}")
            return self._rule_based_reply(user_message, intent, data_result)

    def _rule_based_reply(self, user_message: str, intent: str,
                           data_result: Optional[Dict]) -> str:
        """基于规则的回复（无 AI API 时的后备方案）"""
        if data_result:
            dtype = data_result.get("type", "")
            summary = data_result.get("summary", "")
            data = data_result.get("data", {})

            if dtype == "sales_trend":
                lines = ["📈 **销售趋势分析**\n"]
                for row in data[-3:]:
                    lines.append(
                        f"• {row.get('period_str','')}: "
                        f"销售额 ¥{row.get('total_amount',0):,.0f}, "
                        f"利润 ¥{row.get('total_profit',0):,.0f}"
                    )
                return "\n".join(lines)

            elif dtype == "region_analysis":
                lines = ["🗺 **区域销售分析**\n"]
                for row in data[:5]:
                    lines.append(
                        f"• {row.get('region','')}: "
                        f"¥{row.get('total_amount',0):,.0f} "
                        f"(占比 {row.get('revenue_share',0):.1f}%)"
                    )
                return "\n".join(lines)

            elif dtype == "report_generated":
                return f"✅ 报表已生成！\n路径: {data_result.get('report_path','')}"

            else:
                return f"✅ 数据分析完成：{summary}"

        # 通用回复
        replies = {
            "sales_trend": "请提供具体时间范围，我可以为您分析销售趋势。",
            "region_analysis": "请稍等，正在获取区域销售数据...",
            "product_analysis": "请稍等，正在分析产品销售情况...",
            "rfm_analysis": "正在进行 RFM 客户价值分析...",
            "generate_report": "正在为您生成分析报告，请稍候...",
            "general": f"您好！我是业务分析助手。您询问的是：「{user_message}」\n\n请上传数据文件或指定查询条件，我可以为您提供数据分析和业务洞察。",
        }
        return replies.get(intent, replies["general"])

    def clear_session(self, session_id: str):
        """清除会话历史"""
        if session_id in self._sessions:
            del self._sessions[session_id]
