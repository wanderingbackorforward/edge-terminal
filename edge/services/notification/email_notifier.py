"""
Email Notification Service
Sends email alerts for warning events
Implements Feature 003 - Real-Time Warning System (FR-011)
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from edge.models.warning_event import WarningEvent

logger = logging.getLogger(__name__)


class EmailNotifier:
    """
    Send email notifications for warning events

    Supports multiple SMTP providers (Gmail, SendGrid, AWS SES, generic SMTP)
    Uses threading to avoid blocking warning generation
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_address: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 30
    ):
        """
        Initialize email notifier

        Args:
            smtp_host: SMTP server hostname (e.g., smtp.gmail.com)
            smtp_port: SMTP server port (587 for TLS, 465 for SSL, 25 for plain)
            smtp_user: SMTP authentication username
            smtp_password: SMTP authentication password
            from_address: Email address to send from
            use_tls: Use STARTTLS encryption (port 587)
            use_ssl: Use SSL encryption (port 465)
            timeout: Connection timeout in seconds
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout

        # Thread pool for async email sending
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="email-notifier")

        logger.info(
            f"EmailNotifier initialized: {smtp_host}:{smtp_port} "
            f"(TLS={use_tls}, SSL={use_ssl})"
        )

    def send_warning(
        self,
        warning: WarningEvent,
        to_addresses: List[str],
        cc_addresses: Optional[List[str]] = None
    ) -> bool:
        """
        Send email notification for a warning event (blocking)

        Args:
            warning: Warning event to notify about
            to_addresses: List of recipient email addresses
            cc_addresses: Optional CC recipients

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Build email message
            subject = self._build_subject(warning)
            body_html = self._build_html_body(warning)
            body_text = self._build_text_body(warning)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = ", ".join(to_addresses)
            if cc_addresses:
                msg["Cc"] = ", ".join(cc_addresses)

            # Attach plain text and HTML versions
            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            # Send email via SMTP
            all_recipients = to_addresses + (cc_addresses or [])
            self._send_smtp(msg, all_recipients)

            logger.info(
                f"Email sent for warning {warning.warning_id}: "
                f"{warning.warning_level} - {warning.indicator_name} "
                f"to {len(all_recipients)} recipients"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send email for warning {warning.warning_id}: {e}",
                exc_info=True
            )
            return False

    async def send_warning_async(
        self,
        warning: WarningEvent,
        to_addresses: List[str],
        cc_addresses: Optional[List[str]] = None
    ) -> bool:
        """
        Send email notification asynchronously (non-blocking)

        Args:
            warning: Warning event to notify about
            to_addresses: List of recipient email addresses
            cc_addresses: Optional CC recipients

        Returns:
            True if email sent successfully, False otherwise
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.send_warning,
            warning,
            to_addresses,
            cc_addresses
        )

    def send_batch(
        self,
        warnings: List[WarningEvent],
        to_addresses: List[str],
        cc_addresses: Optional[List[str]] = None
    ) -> int:
        """
        Send batch email summarizing multiple warnings

        Args:
            warnings: List of warning events
            to_addresses: Recipient email addresses
            cc_addresses: Optional CC recipients

        Returns:
            Number of warnings included (0 if send failed)
        """
        if not warnings:
            return 0

        try:
            subject = self._build_batch_subject(warnings)
            body_html = self._build_batch_html_body(warnings)
            body_text = self._build_batch_text_body(warnings)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = ", ".join(to_addresses)
            if cc_addresses:
                msg["Cc"] = ", ".join(cc_addresses)

            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            all_recipients = to_addresses + (cc_addresses or [])
            self._send_smtp(msg, all_recipients)

            logger.info(
                f"Batch email sent: {len(warnings)} warnings "
                f"to {len(all_recipients)} recipients"
            )
            return len(warnings)

        except Exception as e:
            logger.error(f"Failed to send batch email: {e}", exc_info=True)
            return 0

    def _send_smtp(self, msg: MIMEMultipart, recipients: List[str]):
        """Send email via SMTP with proper encryption"""
        if self.use_ssl:
            # Use SMTP_SSL for port 465
            with smtplib.SMTP_SSL(
                self.smtp_host, self.smtp_port, timeout=self.timeout
            ) as server:
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg, to_addrs=recipients)
        else:
            # Use regular SMTP with optional STARTTLS for port 587/25
            with smtplib.SMTP(
                self.smtp_host, self.smtp_port, timeout=self.timeout
            ) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg, to_addrs=recipients)

    def _build_subject(self, warning: WarningEvent) -> str:
        """Build email subject line"""
        level_emoji = {
            "ATTENTION": "⚠️",
            "WARNING": "⚠️⚠️",
            "ALARM": "🚨"
        }
        emoji = level_emoji.get(warning.warning_level, "⚠️")

        return (
            f"{emoji} [{warning.warning_level}] Shield Tunneling Alert - "
            f"Ring {warning.ring_number}"
        )

    def _build_text_body(self, warning: WarningEvent) -> str:
        """Build plain text email body"""
        timestamp_str = datetime.fromtimestamp(warning.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        body = f"""
Shield Tunneling Warning Alert
================================

WARNING LEVEL: {warning.warning_level}
TYPE: {warning.warning_type}
RING NUMBER: {warning.ring_number}
TIMESTAMP: {timestamp_str}

INDICATOR: {warning.indicator_name}
"""

        if warning.indicator_value is not None:
            body += f"CURRENT VALUE: {warning.indicator_value:.2f} {warning.indicator_unit or ''}\n"

        if warning.threshold_value is not None:
            body += f"THRESHOLD: {warning.threshold_value:.2f} {warning.indicator_unit or ''}\n"

        if warning.predicted_value is not None:
            body += f"PREDICTED VALUE: {warning.predicted_value:.2f} {warning.indicator_unit or ''}\n"
            if warning.prediction_confidence is not None:
                body += f"CONFIDENCE: {warning.prediction_confidence:.1%}\n"

        body += f"""
STATUS: {warning.status}
WARNING ID: {warning.warning_id}

================================
This is an automated alert from the Shield Tunneling Intelligent Control Platform.
Please acknowledge this warning in the control system.
"""
        return body

    def _build_html_body(self, warning: WarningEvent) -> str:
        """Build HTML email body with formatting"""
        timestamp_str = datetime.fromtimestamp(warning.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Color coding by warning level
        level_colors = {
            "ATTENTION": "#FFA500",  # Orange
            "WARNING": "#FF8C00",    # Dark orange
            "ALARM": "#DC143C"       # Crimson
        }
        color = level_colors.get(warning.warning_level, "#FFA500")

        html = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .field {{ margin: 10px 0; }}
        .label {{ font-weight: bold; color: #333; }}
        .value {{ color: #666; }}
        .footer {{ margin-top: 20px; padding: 10px; text-align: center; font-size: 12px; color: #999; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>{warning.warning_level} ALERT</h2>
            <p>Ring {warning.ring_number}</p>
        </div>
        <div class="content">
            <div class="field">
                <span class="label">Type:</span>
                <span class="value">{warning.warning_type}</span>
            </div>
            <div class="field">
                <span class="label">Timestamp:</span>
                <span class="value">{timestamp_str}</span>
            </div>
            <div class="field">
                <span class="label">Indicator:</span>
                <span class="value">{warning.indicator_name}</span>
            </div>
"""

        if warning.indicator_value is not None:
            html += f"""
            <div class="field">
                <span class="label">Current Value:</span>
                <span class="value">{warning.indicator_value:.2f} {warning.indicator_unit or ''}</span>
            </div>
"""

        if warning.threshold_value is not None:
            html += f"""
            <div class="field">
                <span class="label">Threshold:</span>
                <span class="value">{warning.threshold_value:.2f} {warning.indicator_unit or ''}</span>
            </div>
"""

        if warning.predicted_value is not None:
            html += f"""
            <div class="field">
                <span class="label">Predicted Value:</span>
                <span class="value">{warning.predicted_value:.2f} {warning.indicator_unit or ''}</span>
            </div>
"""
            if warning.prediction_confidence is not None:
                html += f"""
            <div class="field">
                <span class="label">Confidence:</span>
                <span class="value">{warning.prediction_confidence:.1%}</span>
            </div>
"""

        html += f"""
            <div class="field">
                <span class="label">Status:</span>
                <span class="value">{warning.status}</span>
            </div>
            <div class="field">
                <span class="label">Warning ID:</span>
                <span class="value">{warning.warning_id}</span>
            </div>
        </div>
        <div class="footer">
            <p>Shield Tunneling Intelligent Control Platform</p>
            <p>Automated alert - Please acknowledge in the control system</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _build_batch_subject(self, warnings: List[WarningEvent]) -> str:
        """Build subject for batch email"""
        alarm_count = sum(1 for w in warnings if w.warning_level == "ALARM")
        warning_count = sum(1 for w in warnings if w.warning_level == "WARNING")
        attention_count = sum(1 for w in warnings if w.warning_level == "ATTENTION")

        return (
            f"🚨 Shield Tunneling Alert Summary - "
            f"{len(warnings)} warnings "
            f"({alarm_count} ALARM, {warning_count} WARNING, {attention_count} ATTENTION)"
        )

    def _build_batch_text_body(self, warnings: List[WarningEvent]) -> str:
        """Build plain text body for batch email"""
        body = """
Shield Tunneling Warning Summary
==================================

"""
        for i, warning in enumerate(warnings, 1):
            timestamp_str = datetime.fromtimestamp(warning.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            body += f"""
{i}. [{warning.warning_level}] Ring {warning.ring_number}
   Indicator: {warning.indicator_name}
"""
            if warning.indicator_value is not None:
                body += f"   Value: {warning.indicator_value:.2f} {warning.indicator_unit or ''}\n"
            body += f"   Time: {timestamp_str}\n"

        body += """
==================================
View full details in the control system
"""
        return body

    def _build_batch_html_body(self, warnings: List[WarningEvent]) -> str:
        """Build HTML body for batch email"""
        html = """
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background-color: #DC143C; color: white; padding: 20px; text-align: center; }
        .warning-item { border-left: 4px solid #999; margin: 15px 0; padding: 10px; background: #f9f9f9; }
        .warning-item.ALARM { border-left-color: #DC143C; }
        .warning-item.WARNING { border-left-color: #FF8C00; }
        .warning-item.ATTENTION { border-left-color: #FFA500; }
        .footer { margin-top: 20px; text-align: center; font-size: 12px; color: #999; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Warning Summary</h2>
            <p>""" + str(len(warnings)) + """ alerts detected</p>
        </div>
"""

        for i, warning in enumerate(warnings, 1):
            timestamp_str = datetime.fromtimestamp(warning.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            html += f"""
        <div class="warning-item {warning.warning_level}">
            <strong>{i}. [{warning.warning_level}] Ring {warning.ring_number}</strong><br>
            Indicator: {warning.indicator_name}<br>
"""
            if warning.indicator_value is not None:
                html += f"            Value: {warning.indicator_value:.2f} {warning.indicator_unit or ''}<br>\n"
            html += f"            Time: {timestamp_str}<br>\n"
            html += "        </div>\n"

        html += """
        <div class="footer">
            <p>Shield Tunneling Intelligent Control Platform</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def test_connection(self) -> bool:
        """
        Test SMTP connection and authentication

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.use_ssl:
                with smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, timeout=self.timeout
                ) as server:
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
            else:
                with smtplib.SMTP(
                    self.smtp_host, self.smtp_port, timeout=self.timeout
                ) as server:
                    if self.use_tls:
                        server.starttls()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)

            logger.info(f"SMTP connection test successful: {self.smtp_host}:{self.smtp_port}")
            return True

        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}", exc_info=True)
            return False

    def shutdown(self):
        """Shutdown thread pool"""
        self.executor.shutdown(wait=True)
        logger.info("EmailNotifier shut down")
