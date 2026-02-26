"""
钉钉集成模块
DingTalk Integration Module

支持功能:
- 接收钉钉机器人消息
- 发送消息和报告
- 验证消息签名
- 互动卡片消息
"""
import hashlib
import hmac
import base64
import time
import json
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class DingTalkRobotClient:
    """钉钉机器人客户端（Webhook 方式）"""

    def __init__(self, webhook_url: str, secret: str = ""):
        self.webhook_url = webhook_url
        self.secret = secret

    def _get_sign(self) -> tuple[str, str]:
        """生成签名"""
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = quote(base64.b64encode(hmac_code).decode("utf-8"), safe="")
        return timestamp, sign

    async def send_text(self, content: str, at_mobiles: List[str] = None,
                        at_all: bool = False) -> bool:
        """发送文本消息"""
        payload = {
            "msgtype": "text",
            "text": {"content": content},
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": at_all,
            },
        }
        return await self._post(payload)

    async def send_markdown(self, title: str, text: str,
                            at_mobiles: List[str] = None) -> bool:
        """发送 Markdown 消息"""
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
            "at": {"atMobiles": at_mobiles or [], "isAtAll": False},
        }
        return await self._post(payload)

    async def send_action_card(self, title: str, text: str,
                               btns: List[Dict[str, str]]) -> bool:
        """发送可交互卡片"""
        payload = {
            "msgtype": "actionCard",
            "actionCard": {
                "title": title,
                "text": text,
                "btnOrientation": "0",
                "btns": btns,
            },
        }
        return await self._post(payload)

    async def send_report(self, title: str, data: Dict[str, Any]) -> bool:
        """发送格式化报告"""
        lines = [f"## {title}\n"]
        for key, value in data.items():
            if isinstance(value, float):
                lines.append(f"- **{key}**: {value:,.2f}")
            elif isinstance(value, int):
                lines.append(f"- **{key}**: {value:,}")
            else:
                lines.append(f"- **{key}**: {value}")
        text = "\n".join(lines)
        return await self.send_markdown(title, text)

    async def _post(self, payload: Dict[str, Any]) -> bool:
        """发送请求"""
        url = self.webhook_url
        params = {}
        if self.secret:
            timestamp, sign = self._get_sign()
            params = {"timestamp": timestamp, "sign": sign}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, params=params, json=payload)
                result = resp.json()
                success = result.get("errcode", -1) == 0
                if not success:
                    logger.error(f"钉钉消息发送失败: {result}")
                return success
        except Exception as e:
            logger.error(f"钉钉请求异常: {e}")
            return False


class DingTalkAppClient:
    """钉钉应用客户端（Server API 方式）"""

    BASE_URL = "https://oapi.dingtalk.com"
    NEW_BASE_URL = "https://api.dingtalk.com/v1.0"

    def __init__(self, app_key: str, app_secret: str, agent_id: str = ""):
        self.app_key = app_key
        self.app_secret = app_secret
        self.agent_id = agent_id
        self._access_token = None
        self._token_expires_at = 0

    async def get_access_token(self) -> str:
        """获取访问令牌"""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.NEW_BASE_URL}/oauth2/accessToken",
                json={"appKey": self.app_key, "appSecret": self.app_secret}
            )
            data = resp.json()
            if "accessToken" in data:
                self._access_token = data["accessToken"]
                self._token_expires_at = time.time() + data.get("expireIn", 7200)
                return self._access_token
            raise ValueError(f"获取钉钉 Token 失败: {data}")

    def verify_webhook_signature(self, timestamp: str, sign: str,
                                  app_secret: str) -> bool:
        """验证 Webhook 签名"""
        string_to_sign = f"{timestamp}\n{app_secret}"
        hmac_code = hmac.new(
            app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        expected = base64.b64encode(hmac_code).decode("utf-8")
        return expected == sign

    async def send_message_to_user(self, user_id: str, content: str) -> bool:
        """向指定用户发送消息"""
        token = await self.get_access_token()
        payload = {
            "robotCode": self.app_key,
            "userIds": [user_id],
            "msgKey": "sampleText",
            "msgParam": json.dumps({"content": content}),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.NEW_BASE_URL}/robot/oToMessages/batchSend",
                headers={"x-acs-dingtalk-access-token": token},
                json=payload
            )
            result = resp.json()
            return "processQueryKey" in result


class DingTalkMessageHandler:
    """钉钉消息处理器"""

    def __init__(self, robot_client: DingTalkRobotClient = None,
                 app_client: DingTalkAppClient = None, data_processor=None):
        self.robot_client = robot_client
        self.app_client = app_client
        self.data_processor = data_processor

    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """处理钉钉 Webhook 请求"""
        msg_type = payload.get("msgtype", "")
        sender = payload.get("senderNick", "")
        conversation_id = payload.get("conversationId", "")

        logger.info(f"收到钉钉消息 - 类型: {msg_type}, 发送人: {sender}")

        if msg_type == "text":
            text = payload.get("text", {}).get("content", "").strip()
            reply = await self._process_text(text, sender)
            return {"msgtype": "text", "text": {"content": reply}}
        elif msg_type == "file":
            file_name = payload.get("content", {}).get("fileName", "")
            return {
                "msgtype": "text",
                "text": {"content": f"收到文件「{file_name}」，正在处理..."}
            }
        return {"msgtype": "text", "text": {"content": "消息已收到，正在处理。"}}

    async def _process_text(self, text: str, sender: str) -> str:
        """处理文本内容"""
        if "查询" in text or "query" in text.lower():
            if self.data_processor:
                return await self.data_processor.query(text)
            return "查询功能处理中..."

        elif "报表" in text or "report" in text.lower():
            return "📊 正在生成报表，完成后将发送给您..."

        elif "分析" in text or "analyze" in text.lower():
            if self.data_processor:
                return await self.data_processor.analyze(text)
            return "分析功能处理中..."

        elif text in ["帮助", "help", "/help"]:
            return self._get_help_text()

        else:
            if self.data_processor:
                return await self.data_processor.process_natural_language(text)
            return "您好！请发送「帮助」查看使用指南。"

    def _get_help_text(self) -> str:
        return """📊 业务数据分析系统

🔍 查询: 查询 本月销售额 / 查询 华东区数据
📈 分析: 分析 销售趋势 / 分析 客户分布
📋 报表: 报表 月度总结 / 报表 季度对比
💬 自然语言: 直接提问，如「哪个产品利润最高？」

系统支持微信、钉钉、邮件三通道数据接入。"""
