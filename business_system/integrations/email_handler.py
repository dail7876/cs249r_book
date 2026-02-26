"""
邮件集成模块
Email Integration Module

支持功能:
- IMAP 收信监听
- 解析附件（Excel/CSV）
- SMTP 发送报告
- HTML 邮件报告
"""
import imaplib
import smtplib
import email as email_lib
import asyncio
import logging
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from email.header import decode_header
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)


def decode_str(s: str) -> str:
    """解码邮件头字段"""
    if not s:
        return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


class EmailReceiver:
    """邮件接收器（IMAP）"""

    def __init__(self, host: str, port: int, username: str, password: str,
                 upload_dir: str = "/tmp/email_attachments"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._running = False
        self._callbacks: List[Callable] = []

    def add_callback(self, callback: Callable):
        """添加消息处理回调"""
        self._callbacks.append(callback)

    def connect(self) -> imaplib.IMAP4_SSL:
        """建立 IMAP 连接"""
        mail = imaplib.IMAP4_SSL(self.host, self.port)
        mail.login(self.username, self.password)
        return mail

    def fetch_unread(self) -> List[Dict[str, Any]]:
        """获取未读邮件"""
        messages = []
        try:
            mail = self.connect()
            mail.select("INBOX")
            _, data = mail.search(None, "UNSEEN")
            for num in data[0].split():
                msg_data = self._fetch_message(mail, num)
                if msg_data:
                    messages.append(msg_data)
                    # 标记已读
                    mail.store(num, "+FLAGS", "\\Seen")
            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"获取邮件失败: {e}")
        return messages

    def _fetch_message(self, mail: imaplib.IMAP4_SSL,
                       num: bytes) -> Optional[Dict[str, Any]]:
        """获取单封邮件内容"""
        try:
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            subject = decode_str(msg.get("Subject", ""))
            sender = decode_str(msg.get("From", ""))
            date_str = msg.get("Date", "")

            body_text = ""
            attachments = []

            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    filename = decode_str(part.get_filename() or "")
                    if filename:
                        filepath = self.upload_dir / filename
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        attachments.append({
                            "filename": filename,
                            "filepath": str(filepath),
                            "content_type": content_type,
                        })
                        logger.info(f"保存附件: {filename}")

                elif content_type == "text/plain" and not body_text:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body_text = payload.decode(charset, errors="replace")

            return {
                "subject": subject,
                "sender": sender,
                "date": date_str,
                "body": body_text,
                "attachments": attachments,
                "source": "email",
            }
        except Exception as e:
            logger.error(f"解析邮件失败: {e}")
            return None

    async def start_polling(self, interval: int = 60):
        """启动轮询监听"""
        self._running = True
        logger.info(f"邮件监听已启动，间隔: {interval}秒")
        while self._running:
            try:
                messages = self.fetch_unread()
                for msg in messages:
                    for callback in self._callbacks:
                        try:
                            await callback(msg)
                        except Exception as e:
                            logger.error(f"邮件回调异常: {e}")
            except Exception as e:
                logger.error(f"邮件轮询异常: {e}")
            await asyncio.sleep(interval)

    def stop(self):
        """停止轮询"""
        self._running = False


class EmailSender:
    """邮件发送器（SMTP）"""

    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    def send_text(self, to: str | List[str], subject: str, body: str) -> bool:
        """发送纯文本邮件"""
        return self._send(to, subject, body, html=False)

    def send_html(self, to: str | List[str], subject: str, html_body: str,
                  attachments: List[str] = None) -> bool:
        """发送 HTML 邮件，可带附件"""
        return self._send(to, subject, html_body, html=True,
                          attachments=attachments)

    def send_report(self, to: str | List[str], title: str,
                    data: Dict[str, Any], charts_html: str = "") -> bool:
        """发送业务报表邮件"""
        html = self._build_report_html(title, data, charts_html)
        return self.send_html(to, f"📊 {title}", html)

    def _build_report_html(self, title: str, data: Dict[str, Any],
                           charts_html: str = "") -> str:
        """生成报表 HTML"""
        rows = ""
        for key, value in data.items():
            if isinstance(value, float):
                val_str = f"{value:,.2f}"
            elif isinstance(value, int):
                val_str = f"{value:,}"
            else:
                val_str = str(value)
            rows += f"<tr><td style='padding:8px;border:1px solid #ddd;'><b>{key}</b></td>"
            rows += f"<td style='padding:8px;border:1px solid #ddd;'>{val_str}</td></tr>"

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; }}
  h1 {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
  th {{ background: #1a73e8; color: white; padding: 10px; }}
  tr:nth-child(even) {{ background: #f8f9fa; }}
  .footer {{ margin-top: 30px; color: #888; font-size: 12px; }}
</style>
</head>
<body>
  <h1>📊 {title}</h1>
  <table>
    <tr><th>指标</th><th>数值</th></tr>
    {rows}
  </table>
  {charts_html}
  <div class="footer">
    <p>本报告由自动化业务系统生成</p>
  </div>
</body>
</html>"""

    def _send(self, to: str | List[str], subject: str, body: str,
              html: bool = False, attachments: List[str] = None) -> bool:
        """底层发送方法"""
        if isinstance(to, str):
            to = [to]
        try:
            msg = MIMEMultipart("alternative" if html else "mixed")
            msg["From"] = self.username
            msg["To"] = ", ".join(to)
            msg["Subject"] = subject

            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))

            if attachments:
                for filepath in attachments:
                    path = Path(filepath)
                    if path.exists():
                        with open(path, "rb") as f:
                            part = MIMEApplication(f.read(),
                                                   Name=path.name)
                        part["Content-Disposition"] = (
                            f'attachment; filename="{path.name}"'
                        )
                        msg.attach(part)

            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.username, to, msg.as_string())
            logger.info(f"邮件发送成功: {subject} -> {to}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
