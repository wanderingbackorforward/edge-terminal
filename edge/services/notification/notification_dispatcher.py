"""
Notification Dispatcher Service (T207)
Dispatches notifications through configured channels (Email, SMS, Webhook, etc.)
"""
import logging
import asyncio
import smtplib
import ssl
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiohttp

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    """Abstract base class for notification channels"""

    def __init__(self, channel_id: int, channel_name: str, config: Dict[str, Any]):
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.config = config
        self.is_enabled = True

    @abstractmethod
    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send notification through this channel

        Args:
            recipient: Recipient address (email, phone, URL, etc.)
            subject: Notification subject/title
            message: Notification body
            metadata: Additional context

        Returns:
            Dict with send result: {success: bool, error: str, ...}
        """
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Test channel connectivity"""
        pass


class EmailChannel(NotificationChannel):
    """Email notification channel using SMTP"""

    def __init__(self, channel_id: int, channel_name: str, config: Dict[str, Any]):
        super().__init__(channel_id, channel_name, config)
        self.smtp_host = config.get("smtp_host", "localhost")
        self.smtp_port = config.get("smtp_port", 587)
        self.smtp_user = config.get("smtp_user")
        self.smtp_password = config.get("smtp_password")
        self.from_address = config.get("from_address", "noreply@shield.local")
        self.use_tls = config.get("use_tls", True)

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send email notification"""
        result = {
            "success": False,
            "channel_id": self.channel_id,
            "recipient": recipient,
            "sent_at": None,
            "error": None,
        }

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = recipient

            # Add plain text part
            text_part = MIMEText(message, "plain", "utf-8")
            msg.attach(text_part)

            # Add HTML part if message contains HTML markers
            if "<" in message and ">" in message:
                html_part = MIMEText(message, "html", "utf-8")
                msg.attach(html_part)

            # Send via SMTP
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg)

            result["success"] = True
            result["sent_at"] = datetime.utcnow().isoformat()
            logger.info(f"Email sent to {recipient}: {subject}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to send email to {recipient}: {e}")

        return result

    def _send_smtp(self, msg):
        """Synchronous SMTP send (run in executor)"""
        context = ssl.create_default_context()

        if self.use_tls:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

    async def test_connection(self) -> Dict[str, Any]:
        """Test SMTP connection"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._test_smtp)
            return {"success": True, "message": "SMTP connection successful"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _test_smtp(self):
        """Synchronous SMTP test"""
        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
            if self.use_tls:
                server.starttls(context=context)
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.noop()


class SMSChannel(NotificationChannel):
    """SMS notification channel (via HTTP API)"""

    def __init__(self, channel_id: int, channel_name: str, config: Dict[str, Any]):
        super().__init__(channel_id, channel_name, config)
        self.api_url = config.get("api_url")
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.from_number = config.get("from_number")
        self.provider = config.get("provider", "generic")

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send SMS notification"""
        result = {
            "success": False,
            "channel_id": self.channel_id,
            "recipient": recipient,
            "sent_at": None,
            "error": None,
        }

        if not self.api_url:
            result["error"] = "SMS API URL not configured"
            return result

        try:
            # Combine subject and message for SMS
            sms_text = f"[{subject}] {message}"
            if len(sms_text) > 160:
                sms_text = sms_text[:157] + "..."

            # Generic HTTP API call
            payload = {
                "to": recipient,
                "from": self.from_number,
                "message": sms_text,
                "api_key": self.api_key,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status in (200, 201, 202):
                        result["success"] = True
                        result["sent_at"] = datetime.utcnow().isoformat()
                        logger.info(f"SMS sent to {recipient}")
                    else:
                        result["error"] = f"HTTP {response.status}"

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to send SMS to {recipient}: {e}")

        return result

    async def test_connection(self) -> Dict[str, Any]:
        """Test SMS API connection"""
        if not self.api_url:
            return {"success": False, "error": "API URL not configured"}

        try:
            async with aiohttp.ClientSession() as session:
                # Just check if API is reachable
                async with session.get(
                    self.api_url.rstrip("/") + "/health",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return {"success": response.status < 500}
        except Exception as e:
            return {"success": False, "error": str(e)}


class WebhookChannel(NotificationChannel):
    """Webhook notification channel (HTTP POST)"""

    def __init__(self, channel_id: int, channel_name: str, config: Dict[str, Any]):
        super().__init__(channel_id, channel_name, config)
        self.url = config.get("url")
        self.headers = config.get("headers", {})
        self.method = config.get("method", "POST")
        self.secret = config.get("secret")

    async def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send webhook notification"""
        result = {
            "success": False,
            "channel_id": self.channel_id,
            "recipient": self.url,
            "sent_at": None,
            "error": None,
        }

        webhook_url = recipient or self.url
        if not webhook_url:
            result["error"] = "Webhook URL not configured"
            return result

        try:
            payload = {
                "event": "notification",
                "subject": subject,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }

            headers = dict(self.headers)
            headers.setdefault("Content-Type", "application/json")

            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=self.method,
                    url=webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status < 300:
                        result["success"] = True
                        result["sent_at"] = datetime.utcnow().isoformat()
                        logger.info(f"Webhook sent to {webhook_url}")
                    else:
                        result["error"] = f"HTTP {response.status}"

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to send webhook to {webhook_url}: {e}")

        return result

    async def test_connection(self) -> Dict[str, Any]:
        """Test webhook connectivity"""
        if not self.url:
            return {"success": False, "error": "URL not configured"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    self.url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return {
                        "success": response.status < 500,
                        "status_code": response.status,
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}


class NotificationDispatcher:
    """
    Central notification dispatcher that routes notifications to appropriate channels

    Supports:
    - Multiple channel types (email, SMS, webhook)
    - Subscription-based routing
    - Quiet hours filtering
    - Rate limiting
    """

    def __init__(self):
        self.channels: Dict[int, NotificationChannel] = {}
        self._last_sent: Dict[str, datetime] = {}  # Rate limiting

        logger.info("NotificationDispatcher initialized")

    def register_channel(self, channel: NotificationChannel):
        """Register a notification channel"""
        self.channels[channel.channel_id] = channel
        logger.info(f"Registered channel: {channel.channel_name} ({channel.__class__.__name__})")

    def create_channel(
        self,
        channel_id: int,
        channel_type: str,
        channel_name: str,
        config: Dict[str, Any],
    ) -> NotificationChannel:
        """Factory method to create appropriate channel type"""
        channel_classes = {
            "email": EmailChannel,
            "sms": SMSChannel,
            "webhook": WebhookChannel,
        }

        channel_class = channel_classes.get(channel_type.lower())
        if not channel_class:
            raise ValueError(f"Unknown channel type: {channel_type}")

        channel = channel_class(channel_id, channel_name, config)
        self.register_channel(channel)
        return channel

    async def dispatch(
        self,
        channel_id: int,
        recipient: str,
        subject: str,
        message: str,
        event_type: str = "notification",
        event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        min_interval_seconds: int = 300,
    ) -> Dict[str, Any]:
        """
        Dispatch a notification through specified channel

        Args:
            channel_id: Channel to use
            recipient: Recipient address
            subject: Notification subject
            message: Notification body
            event_type: Type of event triggering notification
            event_id: ID of the triggering event
            metadata: Additional context
            min_interval_seconds: Minimum seconds between notifications to same recipient

        Returns:
            Result dict with success status and details
        """
        # Check channel exists
        channel = self.channels.get(channel_id)
        if not channel:
            return {"success": False, "error": f"Channel {channel_id} not found"}

        if not channel.is_enabled:
            return {"success": False, "error": "Channel is disabled"}

        # Rate limiting
        rate_key = f"{channel_id}:{recipient}"
        last_sent = self._last_sent.get(rate_key)
        if last_sent:
            elapsed = (datetime.utcnow() - last_sent).total_seconds()
            if elapsed < min_interval_seconds:
                return {
                    "success": False,
                    "error": f"Rate limited, retry in {min_interval_seconds - elapsed:.0f}s",
                }

        # Send notification
        result = await channel.send(
            recipient=recipient,
            subject=subject,
            message=message,
            metadata={
                "event_type": event_type,
                "event_id": event_id,
                **(metadata or {}),
            },
        )

        # Update rate limit tracker
        if result.get("success"):
            self._last_sent[rate_key] = datetime.utcnow()

        return result

    async def dispatch_to_multiple(
        self,
        notifications: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Dispatch multiple notifications in parallel

        Args:
            notifications: List of notification dicts with keys:
                - channel_id
                - recipient
                - subject
                - message
                - metadata (optional)

        Returns:
            List of results for each notification
        """
        tasks = []
        for notif in notifications:
            task = self.dispatch(
                channel_id=notif["channel_id"],
                recipient=notif["recipient"],
                subject=notif["subject"],
                message=notif["message"],
                event_type=notif.get("event_type", "notification"),
                event_id=notif.get("event_id"),
                metadata=notif.get("metadata"),
            )
            tasks.append(task)

        return await asyncio.gather(*tasks)

    async def test_channel(self, channel_id: int) -> Dict[str, Any]:
        """Test a channel's connectivity"""
        channel = self.channels.get(channel_id)
        if not channel:
            return {"success": False, "error": f"Channel {channel_id} not found"}

        return await channel.test_connection()

    def is_in_quiet_hours(
        self,
        quiet_start: Optional[time],
        quiet_end: Optional[time],
    ) -> bool:
        """Check if current time is within quiet hours"""
        if not quiet_start or not quiet_end:
            return False

        now = datetime.utcnow().time()

        if quiet_start <= quiet_end:
            # Normal range (e.g., 22:00 to 23:00)
            return quiet_start <= now <= quiet_end
        else:
            # Overnight range (e.g., 22:00 to 06:00)
            return now >= quiet_start or now <= quiet_end


# Singleton instance
_dispatcher: Optional[NotificationDispatcher] = None


def get_notification_dispatcher() -> NotificationDispatcher:
    """Get or create singleton NotificationDispatcher instance"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
