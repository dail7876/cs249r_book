"""
邮件数据接入模块（IMAP 收件 + SMTP 发件）
Email Data Ingestion Module (IMAP receive + SMTP send)
"""
import asyncio
import os
import re
import email
import email.header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

import aiosmtplib
import imapclient
from loguru import logger

from config import settings


@dataclass
class EmailMessage:
    """标准化邮件消息结构"""
    uid: str
    subject: str
    sender: str
    recipients: List[str]
    body_text: str
    body_html: str
    received_at: datetime
    attachments: List[dict] = field(default_factory=list)
    raw_headers: dict = field(default_factory=dict)


def _decode_header(header_value: str) -> str:
    """解码邮件头部（处理 Base64/QP 编码）"""
    parts = email.header.decode_header(header_value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return "".join(decoded)


class EmailReceiver:
    """
    IMAP 邮件接收器
    支持轮询新邮件、自动提取附件（Excel/CSV 数据文件）
    """

    def __init__(self):
        self.imap_host = settings.EMAIL_IMAP_HOST
        self.imap_port = settings.EMAIL_IMAP_PORT
        self.smtp_host = settings.EMAIL_SMTP_HOST
        self.smtp_port = settings.EMAIL_SMTP_PORT
        self.user = settings.EMAIL_USER
        self.password = settings.EMAIL_PASSWORD
        self._handlers: List[Callable] = []
        self._polling_task: Optional[asyncio.Task] = None

    # ── 连接 IMAP ──────────────────────────────────────────────────────────────
    def _connect_imap(self) -> imapclient.IMAPClient:
        client = imapclient.IMAPClient(self.imap_host, port=self.imap_port, ssl=True)
        client.login(self.user, self.password)
        return client

    # ── 解析邮件 ───────────────────────────────────────────────────────────────
    def _parse_email(self, uid: int, raw_email: bytes) -> EmailMessage:
        msg = email.message_from_bytes(raw_email)
        subject = _decode_header(msg.get("Subject", "(无主题)"))
        sender = _decode_header(msg.get("From", ""))
        recipients = [_decode_header(r) for r in msg.get_all("To", [])]
        date_str = msg.get("Date", "")
        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_str)
        except Exception:
            received_at = datetime.utcnow()

        body_text = ""
        body_html = ""
        attachments = []

        for part in msg.walk():
            ct = part.get_content_type()
            cd = part.get("Content-Disposition", "")
            if part.get_content_maintype() == "multipart":
                continue
            if "attachment" in cd or part.get_filename():
                filename = _decode_header(part.get_filename() or "attachment")
                data = part.get_payload(decode=True)
                # 保存附件到 uploads 目录
                save_path = os.path.join(settings.UPLOAD_DIR, filename)
                os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(data)
                attachments.append({
                    "filename": filename,
                    "path": save_path,
                    "content_type": ct,
                    "size": len(data)
                })
                logger.info(f"邮件附件已保存: {save_path}")
            elif ct == "text/plain":
                body_text = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
            elif ct == "text/html":
                body_html = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )

        return EmailMessage(
            uid=str(uid),
            subject=subject,
            sender=sender,
            recipients=recipients,
            body_text=body_text,
            body_html=body_html,
            received_at=received_at,
            attachments=attachments,
            raw_headers=dict(msg.items())
        )

    # ── 获取未读邮件 ───────────────────────────────────────────────────────────
    def fetch_unseen(self, folder: str = "INBOX") -> List[EmailMessage]:
        if not self.user or not self.password:
            logger.warning("邮件账户未配置，跳过邮件检查")
            return []
        messages = []
        try:
            client = self._connect_imap()
            client.select_folder(folder)
            uids = client.search(["UNSEEN"])
            if uids:
                logger.info(f"发现 {len(uids)} 封未读邮件")
                data = client.fetch(uids, ["RFC822"])
                for uid, msg_data in data.items():
                    raw = msg_data[b"RFC822"]
                    try:
                        parsed = self._parse_email(uid, raw)
                        messages.append(parsed)
                        client.set_flags([uid], [imapclient.SEEN])
                    except Exception as e:
                        logger.error(f"解析邮件 {uid} 失败: {e}")
            client.logout()
        except Exception as e:
            logger.error(f"IMAP 连接错误: {e}")
        return messages

    # ── 发送邮件 ───────────────────────────────────────────────────────────────
    async def send_email(self, to: List[str], subject: str,
                          body_html: str, body_text: str = "",
                          attachments: Optional[List[str]] = None) -> bool:
        if not self.user or not self.password:
            logger.warning("邮件账户未配置，无法发送")
            return False
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = ", ".join(to)
        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        for att_path in (attachments or []):
            with open(att_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(att_path)}"'
            )
            msg.attach(part)
        try:
            async with aiosmtplib.SMTP(hostname=self.smtp_host,
                                        port=self.smtp_port,
                                        use_tls=False) as smtp:
                await smtp.starttls()
                await smtp.login(self.user, self.password)
                await smtp.send_message(msg)
            logger.info(f"邮件已发送至: {to}")
            return True
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return False

    # ── 自动轮询 ───────────────────────────────────────────────────────────────
    async def start_polling(self, interval: int = None):
        interval = interval or settings.EMAIL_CHECK_INTERVAL
        logger.info(f"启动邮件轮询，间隔: {interval}s")
        while True:
            try:
                messages = self.fetch_unseen()
                for msg in messages:
                    await self.dispatch(msg)
            except Exception as e:
                logger.error(f"邮件轮询错误: {e}")
            await asyncio.sleep(interval)

    def register_handler(self, handler: Callable):
        self._handlers.append(handler)

    async def dispatch(self, message: EmailMessage):
        for handler in self._handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"邮件处理器错误: {e}")


email_receiver = EmailReceiver()
