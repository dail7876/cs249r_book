"""
钉钉机器人 / 企业内部应用 数据接入模块
DingTalk Robot / Enterprise App Data Ingestion Module
"""
import time
import hmac
import base64
import hashlib
import json
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum

import httpx
from loguru import logger

from config import settings


class DingMsgType(str, Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    ACTION_CARD = "actionCard"
    FILE = "file"
    MIXED = "mixed"


@dataclass
class DingTalkMessage:
    """标准化钉钉消息结构"""
    msg_id: str
    sender_id: str
    sender_name: str
    conversation_id: str
    msg_type: DingMsgType
    content: str
    timestamp: int
    at_users: List[str] = field(default_factory=list)
    file_url: Optional[str] = None
    raw: Optional[Dict] = None


class DingTalkReceiver:
    """
    钉钉消息接收器
    支持：钉钉自定义机器人 + 企业内部应用消息
    """

    def __init__(self):
        self.app_key = settings.DINGTALK_APP_KEY
        self.app_secret = settings.DINGTALK_APP_SECRET
        self.robot_webhook = settings.DINGTALK_ROBOT_WEBHOOK
        self.robot_secret = settings.DINGTALK_ROBOT_SECRET
        self._access_token: Optional[str] = None
        self._token_expires: float = 0.0
        self._handlers: list[Callable] = []

    # ── 签名生成 (用于发送消息时验签) ─────────────────────────────────────────
    def _generate_sign(self) -> tuple[str, str]:
        timestamp = str(round(time.time() * 1000))
        secret = self.robot_secret or ""
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return timestamp, sign

    # ── 接收消息验签 ───────────────────────────────────────────────────────────
    def verify_webhook_sign(self, timestamp: str, sign: str) -> bool:
        secret = self.robot_secret or ""
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        expected = base64.b64encode(hmac_code).decode("utf-8")
        return expected == sign

    # ── 解析钉钉 Webhook 消息 ──────────────────────────────────────────────────
    def parse_webhook_message(self, body: Dict) -> DingTalkMessage:
        msg_type_str = body.get("msgtype", "text")
        try:
            msg_type = DingMsgType(msg_type_str)
        except ValueError:
            msg_type = DingMsgType.TEXT

        text_obj = body.get("text", {})
        content = text_obj.get("content", "") if isinstance(text_obj, dict) else str(text_obj)

        sender = body.get("senderNick", body.get("senderId", "unknown"))
        return DingTalkMessage(
            msg_id=body.get("msgId", str(int(time.time()))),
            sender_id=body.get("senderId", ""),
            sender_name=sender,
            conversation_id=body.get("conversationId", ""),
            msg_type=msg_type,
            content=content.strip(),
            timestamp=body.get("createAt", int(time.time() * 1000)),
            at_users=[u.get("dingtalkId", "") for u in body.get("atUsers", [])],
            raw=body
        )

    # ── Token 获取 ─────────────────────────────────────────────────────────────
    async def get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token
        async with httpx.AsyncClient() as client:
            url = "https://oapi.dingtalk.com/gettoken"
            resp = await client.get(url, params={
                "appkey": self.app_key,
                "appsecret": self.app_secret
            })
            data = resp.json()
            if data.get("errcode", -1) != 0:
                raise RuntimeError(f"获取钉钉 AccessToken 失败: {data}")
            self._access_token = data["access_token"]
            self._token_expires = time.time() + data["expires_in"] - 60
            logger.info("钉钉 AccessToken 已刷新")
            return self._access_token

    # ── 发送机器人消息 ─────────────────────────────────────────────────────────
    async def send_robot_text(self, content: str,
                               at_mobiles: Optional[List[str]] = None,
                               at_all: bool = False) -> bool:
        if not self.robot_webhook:
            logger.warning("钉钉机器人 Webhook 未配置")
            return False

        timestamp, sign = self._generate_sign()
        params = {"timestamp": timestamp, "sign": sign}
        payload: Dict[str, Any] = {
            "msgtype": "text",
            "text": {"content": content},
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": at_all
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.robot_webhook, json=payload, params=params)
            data = resp.json()
            ok = data.get("errcode", -1) == 0
            if not ok:
                logger.error(f"钉钉机器人发送失败: {data}")
            return ok

    async def send_robot_markdown(self, title: str, content: str,
                                   at_mobiles: Optional[List[str]] = None) -> bool:
        if not self.robot_webhook:
            return False
        timestamp, sign = self._generate_sign()
        params = {"timestamp": timestamp, "sign": sign}
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": content},
            "at": {"atMobiles": at_mobiles or [], "isAtAll": False}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.robot_webhook, json=payload, params=params)
            return resp.json().get("errcode", -1) == 0

    async def send_robot_action_card(self, title: str, text: str,
                                      buttons: List[Dict[str, str]]) -> bool:
        if not self.robot_webhook:
            return False
        timestamp, sign = self._generate_sign()
        params = {"timestamp": timestamp, "sign": sign}
        payload = {
            "msgtype": "actionCard",
            "actionCard": {
                "title": title,
                "text": text,
                "btns": buttons,
                "btnOrientation": "0"
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.robot_webhook, json=payload, params=params)
            return resp.json().get("errcode", -1) == 0

    # ── 发送工作通知 ───────────────────────────────────────────────────────────
    async def send_work_notice(self, user_id_list: List[str],
                                content: str, msg_type: str = "text") -> bool:
        token = await self.get_access_token()
        url = "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2"
        payload = {
            "agent_id": self.app_key,
            "userid_list": ",".join(user_id_list),
            "msg": {"msgtype": msg_type, msg_type: {"content": content}}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                params={"access_token": token}
            )
            data = resp.json()
            return data.get("errcode", -1) == 0

    def register_handler(self, handler: Callable):
        self._handlers.append(handler)

    async def dispatch(self, message: DingTalkMessage):
        for handler in self._handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"钉钉消息处理器错误: {e}")


dingtalk_receiver = DingTalkReceiver()
