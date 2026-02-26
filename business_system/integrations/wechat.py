"""
微信企业号/企业微信集成模块
WeChat Work Integration Module

支持功能:
- 接收企业微信消息
- 发送消息和报告
- 处理文件上传
- 验证消息签名
"""
import hashlib
import time
import xml.etree.ElementTree as ET
import json
import logging
import hmac
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class WeChatWorkClient:
    """企业微信客户端"""

    BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(self, corp_id: str, corp_secret: str, agent_id: str,
                 token: str = "", encoding_aes_key: str = ""):
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self.token = token
        self.encoding_aes_key = encoding_aes_key
        self._access_token = None
        self._token_expires_at = 0

    async def get_access_token(self) -> str:
        """获取访问令牌"""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/gettoken",
                params={"corpid": self.corp_id, "corpsecret": self.corp_secret}
            )
            data = resp.json()
            if data.get("errcode", 0) == 0:
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data["expires_in"]
                return self._access_token
            raise ValueError(f"获取微信 Token 失败: {data}")

    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        """验证消息签名"""
        params = sorted([self.token, timestamp, nonce])
        string = "".join(params)
        computed = hashlib.sha1(string.encode()).hexdigest()
        return computed == signature

    def parse_xml_message(self, xml_body: str) -> Dict[str, Any]:
        """解析企业微信 XML 消息"""
        try:
            root = ET.fromstring(xml_body)
            msg = {}
            for child in root:
                msg[child.tag] = child.text
            return msg
        except ET.ParseError as e:
            logger.error(f"XML 解析失败: {e}")
            return {}

    async def send_text_message(self, to_user: str, content: str) -> bool:
        """发送文本消息"""
        token = await self.get_access_token()
        payload = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": self.agent_id,
            "text": {"content": content},
            "safe": 0,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/message/send",
                params={"access_token": token},
                json=payload
            )
            result = resp.json()
            return result.get("errcode", -1) == 0

    async def send_markdown_message(self, to_user: str, content: str) -> bool:
        """发送 Markdown 消息"""
        token = await self.get_access_token()
        payload = {
            "touser": to_user,
            "msgtype": "markdown",
            "agentid": self.agent_id,
            "markdown": {"content": content},
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/message/send",
                params={"access_token": token},
                json=payload
            )
            result = resp.json()
            return result.get("errcode", -1) == 0

    async def send_file_message(self, to_user: str, media_id: str) -> bool:
        """发送文件消息"""
        token = await self.get_access_token()
        payload = {
            "touser": to_user,
            "msgtype": "file",
            "agentid": self.agent_id,
            "file": {"media_id": media_id},
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/message/send",
                params={"access_token": token},
                json=payload
            )
            result = resp.json()
            return result.get("errcode", -1) == 0

    async def upload_media(self, file_path: str, media_type: str = "file") -> Optional[str]:
        """上传媒体文件，返回 media_id"""
        token = await self.get_access_token()
        with open(file_path, "rb") as f:
            files = {"media": f}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.BASE_URL}/media/upload",
                    params={"access_token": token, "type": media_type},
                    files=files
                )
                result = resp.json()
                if result.get("errcode", -1) == 0:
                    return result.get("media_id")
        return None

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户信息"""
        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/user/get",
                params={"access_token": token, "userid": user_id}
            )
            return resp.json()


class WeChatMessageHandler:
    """企业微信消息处理器"""

    def __init__(self, client: WeChatWorkClient, data_processor=None):
        self.client = client
        self.data_processor = data_processor

    async def handle_message(self, msg: Dict[str, Any]) -> Optional[str]:
        """处理接收到的消息，返回回复内容"""
        msg_type = msg.get("MsgType", "")
        from_user = msg.get("FromUserName", "")
        content = msg.get("Content", "")

        logger.info(f"收到微信消息 - 类型: {msg_type}, 用户: {from_user}")

        if msg_type == "text":
            return await self._handle_text(from_user, content)
        elif msg_type == "file":
            return await self._handle_file(from_user, msg)
        elif msg_type == "event":
            return await self._handle_event(from_user, msg)
        else:
            return "收到消息，正在处理中..."

    async def _handle_text(self, from_user: str, content: str) -> str:
        """处理文本消息"""
        content = content.strip()

        # 查询指令
        if content.startswith("查询") or content.startswith("query"):
            return await self._process_query(content)
        elif content.startswith("报表") or content.startswith("report"):
            return "正在生成报表，请稍候..."
        elif content.startswith("分析") or content.startswith("analyze"):
            return await self._process_analysis(content)
        elif content in ["帮助", "help", "?"]:
            return self._get_help_text()
        else:
            # 转发到 AI 对话
            if self.data_processor:
                return await self.data_processor.process_natural_language(content)
            return f"收到消息: {content}，请使用「查询」「报表」「分析」等指令。"

    async def _handle_file(self, from_user: str, msg: Dict[str, Any]) -> str:
        """处理文件消息"""
        file_name = msg.get("FileName", "未知文件")
        media_id = msg.get("MediaId", "")
        logger.info(f"收到文件: {file_name}, MediaId: {media_id}")
        return f"收到文件「{file_name}」，正在处理数据，处理完成后将通知您。"

    async def _handle_event(self, from_user: str, msg: Dict[str, Any]) -> Optional[str]:
        """处理事件消息"""
        event = msg.get("Event", "")
        if event == "subscribe":
            return "欢迎使用业务数据分析系统！发送「帮助」查看使用说明。"
        return None

    async def _process_query(self, content: str) -> str:
        """处理查询请求"""
        if self.data_processor:
            result = await self.data_processor.query(content)
            return result
        return "查询功能暂时不可用，请稍后再试。"

    async def _process_analysis(self, content: str) -> str:
        """处理分析请求"""
        if self.data_processor:
            result = await self.data_processor.analyze(content)
            return result
        return "分析功能暂时不可用，请稍后再试。"

    def _get_help_text(self) -> str:
        return """📊 业务数据分析系统使用说明

【数据查询】
• 查询 本月销售额
• 查询 华东区销售情况
• 查询 产品A销量

【数据分析】
• 分析 销售趋势
• 分析 区域对比
• 分析 客户分布

【报表生成】
• 报表 月度销售报告
• 报表 季度市场分析

【自然语言】
直接输入问题，如：
「最近三个月哪个区域销售增长最快？」

如需帮助请联系管理员。"""
