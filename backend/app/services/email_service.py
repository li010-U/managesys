"""邮件发送服务"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    """SMTP 邮件发送服务"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_name: str = "DCIManage 系统",
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_name = from_name
        self.use_tls = use_tls

    def send(
        self,
        to_emails: list[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """发送邮件"""
        if not to_emails:
            logger.warning("收件人列表为空，跳过发送")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.from_name} <{self.smtp_user}>"
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = Header(subject, "utf-8")

            if text_content:
                msg.attach(MIMEText(text_content, "plain", "utf-8"))

            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, to_emails, msg.as_string())

            logger.info(f"邮件发送成功: {subject} -> {to_emails}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP 认证失败，请检查用户名和密码")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP 发送失败: {e}")
            return False
        except Exception as e:
            logger.error(f"邮件发送异常: {e}")
            return False

    def send_alert_email(
        self,
        to_emails: list[str],
        alert_title: str,
        alert_level: str,
        alert_detail: str,
        device_name: Optional[str] = None,
        threshold_value: Optional[str] = None,
    ) -> bool:
        """发送告警邮件"""
        level_colors = {
            "general": "#1890ff",
            "serious": "#ff7a00",
            "emergency": "#f5222d",
        }
        level_labels = {
            "general": "一般告警",
            "serious": "严重告警",
            "emergency": "紧急告警",
        }
        color = level_colors.get(alert_level, "#1890ff")
        level_label = level_labels.get(alert_level, "告警")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        device_html = f'<div class="field"><div class="label">设备名称</div><div class="value">{device_name}</div></div>' if device_name else ""
        threshold_html = f'<div class="field"><div class="label">阈值信息</div><div class="value">{threshold_value}</div></div>' if threshold_value else ""

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .header h2 {{ margin: 0; font-size: 18px; }}
        .content {{ background: #f5f5f5; padding: 20px; border-radius: 0 0 8px 8px; }}
        .field {{ margin-bottom: 12px; }}
        .label {{ color: #666; font-size: 13px; }}
        .value {{ font-weight: 500; margin-top: 2px; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 {level_label}</h2>
        </div>
        <div class="content">
            <div class="field">
                <div class="label">告警标题</div>
                <div class="value">{alert_title}</div>
            </div>
            {device_html}
            <div class="field">
                <div class="label">告警级别</div>
                <div class="value" style="color: {color};">{level_label}</div>
            </div>
            {threshold_html}
            <div class="field">
                <div class="label">告警详情</div>
                <div class="value">{alert_detail}</div>
            </div>
            <div class="field">
                <div class="label">发生时间</div>
                <div class="value">{now_str}</div>
            </div>
        </div>
        <div class="footer">
            此邮件由 DCIManage 系统自动发送，请勿回复
        </div>
    </div>
</body>
</html>
        """

        device_text = f"设备名称: {device_name}\n" if device_name else ""
        threshold_text = f"阈值信息: {threshold_value}\n" if threshold_value else ""

        text_content = f"""
{level_label}

告警标题: {alert_title}
{device_text}告警级别: {level_label}
{threshold_text}告警详情: {alert_detail}
时间: {now_str}

---
此邮件由 DCIManage 系统自动发送
        """

        return self.send(to_emails, f"[{level_label}] {alert_title}", html_content, text_content)


# 全局邮件服务实例（延迟初始化）
_email_service: Optional[EmailService] = None


def init_email_service(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_name: str = "DCIManage 系统",
    use_tls: bool = True,
) -> EmailService:
    """初始化邮件服务"""
    global _email_service
    _email_service = EmailService(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        from_name=from_name,
        use_tls=use_tls,
    )
    return _email_service


def get_email_service() -> Optional[EmailService]:
    """获取邮件服务实例"""
    return _email_service
