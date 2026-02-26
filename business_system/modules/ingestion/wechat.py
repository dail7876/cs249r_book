"""
微信企业号 / 微信群机器人 数据接入模块
WeChat Enterprise / Group Robot Data Ingestion Module
"""
import hashlib
import time
import json
import hmac
import base64
import asyncio
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

import httpx
from loguru import logger

from config import settings


class WeChatMsgType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    EVENT = "event"
    MARKDOWN = "markdown"


@dataclass
class WeChatMessage:
    """标准化微信消息结构"""
    msg_id: str
    from_user: str
    to_user: str
    msg_type: WeChatMsgType
    content: str
    create_time: int
    media_id: Optional[str] = None
    raw: Optional[Dict] = None


class WeChatReceiver:
    """
    微信企业号消息接收器
    支持：企业微信自建应用 + 群机器人 Webhook
    """

    def __init__(self):
        self.corp_id = settings.WECHAT_CORP_ID
        self.corp_secret = settings.WECHAT_CORP_SECRET
        self.agent_id = settings.WECHAT_AGENT_ID
        self.token = settings.WECHAT_TOKEN
        self.aes_key = settings.WECHAT_ENCODING_AES_KEY
        self._access_token: Optional[str] = None
        self._token_expires: float = 0.0
        self._handlers: list[Callable] = []

    # ── Token 管理 ─────────────────────────────────────────────────────────────
    async def get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token
        async with httpx.AsyncClient() as client:
            url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            resp = await client.get(url, params={
                "corpid": self.corp_id,
                "corpsecret": self.corp_secret
            })
            data = resp.json()
            if data.get("errcode", 0) != 0:
                raise RuntimeError(f"获取微信AccessToken失败: {data}")
            self._access_token = data["access_token"]
            self._token_expires = time.time() + data["expires_in"] - 60
            logger.info("微信 AccessToken 已刷新")
            return self._access_token

    # ── 消息验签 ───────────────────────────────────────────────────────────────
    def verify_signature(self, msg_signature: str, timestamp: str,
                         nonce: str, echostr: str = "") -> bool:
        items = sorted([self.token, timestamp, nonce, echostr])
        sha1 = hashlib.sha1("".join(items).encode()).hexdigest()
        return sha1 == msg_signature

    # ── 解析 XML 消息 ──────────────────────────────────────────────────────────
    def parse_xml_message(self, xml_body: str) -> WeChatMessage:
        root = ET.fromstring(xml_body)
        msg_type_str = root.findtext("MsgType", "text")
        try:
            msg_type = WeChatMsgType(msg_type_str)
        except ValueError:
            msg_type = WeChatMsgType.TEXT

        content = root.findtext("Content", "") or root.findtext("MediaId", "")
        return WeChatMessage(
            msg_id=root.findtext("MsgId", str(int(time.time()))),
            from_user=root.findtext("FromUserName", ""),
            to_user=root.findtext("ToUserName", ""),
            msg_type=msg_type,
            content=content,
            create_time=int(root.findtext("CreateTime", str(int(time.time())))),
            media_id=root.findtext("MediaId"),
            raw={"xml": xml_body}
        )

    # ── 发送消息 ───────────────────────────────────────────────────────────────
    async def send_text(self, to_user: str, content: str) -> bool:
        token = await self.get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        payload = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": int(self.agent_id),
            "text": {"content": content},
            "safe": 0
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            ok = data.get("errcode", -1) == 0
            if not ok:
                logger.error(f"微信发送消息失败: {data}")
            return ok

    async def send_markdown(self, to_user: str, content: str) -> bool:
        token = await self.get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        payload = {
            "touser": to_user,
            "msgtype": "markdown",
            "agentid": int(self.agent_id),
            "markdown": {"content": content}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            return data.get("errcode", -1) == 0

    # ── 群机器人 Webhook ───────────────────────────────────────────────────────
    async def send_robot_message(self, content: str, msg_type: str = "text") -> bool:
        if not settings.WECHAT_WEBHOOK_URL:
            logger.warning("微信群机器人 Webhook URL 未配置")
            return False
        payload: Dict[str, Any] = {"msgtype": msg_type}
        if msg_type == "text":
            payload["text"] = {"content": content}
        elif msg_type == "markdown":
            payload["markdown"] = {"content": content}
        async with httpx.AsyncClient() as client:
            resp = await client.post(settings.WECHAT_WEBHOOK_URL, json=payload)
            return resp.status_code == 200

    # ── 下载媒体文件 ───────────────────────────────────────────────────────────
    async def download_media(self, media_id: str, save_path: str) -> bool:
        token = await self.get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={token}&media_id={media_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200 and "application" in resp.headers.get("content-type", ""):
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"微信媒体文件已下载: {save_path}")
                return True
        return False

    def register_handler(self, handler: Callable):
        self._handlers.append(handler)

    async def dispatch(self, message: WeChatMessage):
        for handler in self._handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"微信消息处理器错误: {e}")


wechat_receiver = WeChatReceiver()
