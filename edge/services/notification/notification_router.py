"""
Notification Router
Routes warning events to appropriate notification channels based on severity
Implements Feature 003 - Real-Time Warning System (FR-010 to FR-014)
"""
import logging
from typing import List, Dict, Optional, Any
import asyncio
from datetime import datetime

from edge.models.warning_event import WarningEvent
from edge.services.notification.mqtt_publisher import MQTTPublisher
from edge.services.notification.email_notifier import EmailNotifier
from edge.services.notification.sms_client import SMSClient

logger = logging.getLogger(__name__)


class NotificationRouter:
    """
    Route warning events to appropriate notification channels

    Implements graded response mechanism:
    - ATTENTION: MQTT dashboard notifications only
    - WARNING: MQTT + Email
    - ALARM: MQTT + Email + SMS

    Manages notification recipients and delivery tracking
    """

    def __init__(
        self,
        mqtt_publisher: Optional[MQTTPublisher] = None,
        email_notifier: Optional[EmailNotifier] = None,
        sms_client: Optional[SMSClient] = None,
        notification_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize notification router

        Args:
            mqtt_publisher: MQTT publisher instance
            email_notifier: Email notifier instance
            sms_client: SMS client instance
            notification_config: Configuration dict with recipient lists:
                {
                    "email_recipients": {
                        "WARNING": ["user1@example.com", "user2@example.com"],
                        "ALARM": ["user1@example.com", "manager@example.com"]
                    },
                    "sms_recipients": {
                        "ALARM": ["+1234567890", "+0987654321"]
                    }
                }
        """
        self.mqtt = mqtt_publisher
        self.email = email_notifier
        self.sms = sms_client
        self.config = notification_config or {}

        # Extract recipient lists from config
        self.email_recipients = self.config.get("email_recipients", {})
        self.sms_recipients = self.config.get("sms_recipients", {})

        # Delivery statistics
        self.stats = {
            "mqtt_sent": 0,
            "mqtt_failed": 0,
            "email_sent": 0,
            "email_failed": 0,
            "sms_sent": 0,
            "sms_failed": 0,
        }

        logger.info(
            f"NotificationRouter initialized: "
            f"MQTT={'enabled' if mqtt_publisher else 'disabled'}, "
            f"Email={'enabled' if email_notifier else 'disabled'}, "
            f"SMS={'enabled' if sms_client else 'disabled'}"
        )

    async def route_warning(self, warning: WarningEvent) -> Dict[str, bool]:
        """
        Route a single warning to appropriate channels based on level

        Implements FR-010 to FR-012: Graded response mechanism

        Args:
            warning: Warning event to route

        Returns:
            Dict with channel delivery results:
            {"mqtt": True/False, "email": True/False, "sms": True/False}
        """
        results = {"mqtt": False, "email": False, "sms": False}

        # Determine which channels to use based on warning level
        channels = self._get_channels_for_level(warning.warning_level)

        # Send to MQTT (async)
        if "mqtt" in channels and self.mqtt:
            try:
                await self.mqtt.publish_warning(warning)
                results["mqtt"] = True
                self.stats["mqtt_sent"] += 1
                logger.debug(f"MQTT notification sent for warning {warning.warning_id}")
            except Exception as e:
                logger.error(
                    f"Failed to send MQTT notification for {warning.warning_id}: {e}"
                )
                self.stats["mqtt_failed"] += 1

        # Send email (async)
        if "email" in channels and self.email:
            email_recipients = self._get_email_recipients(warning.warning_level)
            if email_recipients:
                try:
                    success = await self.email.send_warning_async(warning, email_recipients)
                    results["email"] = success
                    if success:
                        self.stats["email_sent"] += 1
                    else:
                        self.stats["email_failed"] += 1
                    logger.debug(
                        f"Email notification {'sent' if success else 'failed'} "
                        f"for warning {warning.warning_id} to {len(email_recipients)} recipients"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send email for {warning.warning_id}: {e}"
                    )
                    self.stats["email_failed"] += 1

        # Send SMS (async)
        if "sms" in channels and self.sms:
            sms_recipients = self._get_sms_recipients(warning.warning_level)
            if sms_recipients:
                try:
                    sent_count = await self.sms.send_warning_async(warning, sms_recipients)
                    results["sms"] = sent_count > 0
                    self.stats["sms_sent"] += sent_count
                    self.stats["sms_failed"] += len(sms_recipients) - sent_count
                    logger.debug(
                        f"SMS notification sent to {sent_count}/{len(sms_recipients)} "
                        f"recipients for warning {warning.warning_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send SMS for {warning.warning_id}: {e}"
                    )
                    self.stats["sms_failed"] += len(sms_recipients)

        return results

    async def route_warnings_batch(
        self, warnings: List[WarningEvent]
    ) -> Dict[str, int]:
        """
        Route multiple warnings to channels

        Args:
            warnings: List of warning events

        Returns:
            Dict with channel delivery counts:
            {"mqtt": 5, "email": 3, "sms": 2}
        """
        if not warnings:
            return {"mqtt": 0, "email": 0, "sms": 0}

        counts = {"mqtt": 0, "email": 0, "sms": 0}

        # Send all to MQTT
        if self.mqtt:
            try:
                await self.mqtt.publish_warnings_batch(warnings)
                counts["mqtt"] = len(warnings)
                self.stats["mqtt_sent"] += len(warnings)
                logger.info(f"MQTT batch notification: {len(warnings)} warnings")
            except Exception as e:
                logger.error(f"Failed to send MQTT batch: {e}")
                self.stats["mqtt_failed"] += len(warnings)

        # Group warnings by level for email/SMS
        warnings_by_level = self._group_warnings_by_level(warnings)

        # Send emails per level
        if self.email:
            for level, level_warnings in warnings_by_level.items():
                recipients = self._get_email_recipients(level)
                if recipients and level_warnings:
                    try:
                        sent_count = self.email.send_batch(level_warnings, recipients)
                        counts["email"] += sent_count
                        self.stats["email_sent"] += 1
                        logger.info(
                            f"Email batch sent: {len(level_warnings)} {level} warnings "
                            f"to {len(recipients)} recipients"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send email batch for {level}: {e}")
                        self.stats["email_failed"] += 1

        # Send individual SMS for each warning (avoid batch to prevent long messages)
        if self.sms:
            for warning in warnings:
                if self._should_send_sms(warning.warning_level):
                    recipients = self._get_sms_recipients(warning.warning_level)
                    if recipients:
                        try:
                            sent_count = await self.sms.send_warning_async(warning, recipients)
                            if sent_count > 0:
                                counts["sms"] += 1
                            self.stats["sms_sent"] += sent_count
                            self.stats["sms_failed"] += len(recipients) - sent_count
                        except Exception as e:
                            logger.error(f"Failed to send SMS for {warning.warning_id}: {e}")
                            self.stats["sms_failed"] += len(recipients)

        return counts

    def _get_channels_for_level(self, warning_level: str) -> List[str]:
        """
        Determine which notification channels to use based on warning level

        Implements FR-010 to FR-012: Graded response mechanism
        - ATTENTION: Dashboard only (MQTT)
        - WARNING: Dashboard + Email
        - ALARM: Dashboard + Email + SMS
        """
        if warning_level == "ALARM":
            return ["mqtt", "email", "sms"]
        elif warning_level == "WARNING":
            return ["mqtt", "email"]
        elif warning_level == "ATTENTION":
            return ["mqtt"]
        else:
            # Unknown level - default to MQTT only
            logger.warning(f"Unknown warning level: {warning_level}, using MQTT only")
            return ["mqtt"]

    def _should_send_sms(self, warning_level: str) -> bool:
        """Check if SMS should be sent for this warning level"""
        return warning_level == "ALARM"

    def _get_email_recipients(self, warning_level: str) -> List[str]:
        """Get email recipients for a warning level"""
        # Try level-specific list first
        recipients = self.email_recipients.get(warning_level, [])

        # Fall back to "all" if no level-specific list
        if not recipients:
            recipients = self.email_recipients.get("all", [])

        return recipients

    def _get_sms_recipients(self, warning_level: str) -> List[str]:
        """Get SMS recipients for a warning level"""
        # Try level-specific list first
        recipients = self.sms_recipients.get(warning_level, [])

        # Fall back to "all" if no level-specific list
        if not recipients:
            recipients = self.sms_recipients.get("all", [])

        return recipients

    def _group_warnings_by_level(
        self, warnings: List[WarningEvent]
    ) -> Dict[str, List[WarningEvent]]:
        """Group warnings by warning level"""
        grouped: Dict[str, List[WarningEvent]] = {
            "ATTENTION": [],
            "WARNING": [],
            "ALARM": []
        }

        for warning in warnings:
            level = warning.warning_level
            if level in grouped:
                grouped[level].append(warning)
            else:
                logger.warning(f"Unknown warning level: {level}")

        return grouped

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get notification delivery statistics

        Returns:
            Dict with delivery counts and success rates
        """
        total_mqtt = self.stats["mqtt_sent"] + self.stats["mqtt_failed"]
        total_email = self.stats["email_sent"] + self.stats["email_failed"]
        total_sms = self.stats["sms_sent"] + self.stats["sms_failed"]

        return {
            "mqtt": {
                "sent": self.stats["mqtt_sent"],
                "failed": self.stats["mqtt_failed"],
                "total": total_mqtt,
                "success_rate": (
                    self.stats["mqtt_sent"] / total_mqtt if total_mqtt > 0 else 0
                )
            },
            "email": {
                "sent": self.stats["email_sent"],
                "failed": self.stats["email_failed"],
                "total": total_email,
                "success_rate": (
                    self.stats["email_sent"] / total_email if total_email > 0 else 0
                )
            },
            "sms": {
                "sent": self.stats["sms_sent"],
                "failed": self.stats["sms_failed"],
                "total": total_sms,
                "success_rate": (
                    self.stats["sms_sent"] / total_sms if total_sms > 0 else 0
                )
            }
        }

    def reset_statistics(self):
        """Reset delivery statistics counters"""
        self.stats = {
            "mqtt_sent": 0,
            "mqtt_failed": 0,
            "email_sent": 0,
            "email_failed": 0,
            "sms_sent": 0,
            "sms_failed": 0,
        }
        logger.info("Notification statistics reset")

    async def test_all_channels(self) -> Dict[str, bool]:
        """
        Test connectivity to all configured notification channels

        Returns:
            Dict with test results for each channel
        """
        results = {"mqtt": False, "email": False, "sms": False}

        # Test MQTT
        if self.mqtt:
            try:
                # Publish test message
                test_warning = WarningEvent(
                    warning_id="test-connection",
                    warning_type="test",
                    warning_level="ATTENTION",
                    ring_number=0,
                    timestamp=datetime.utcnow().timestamp(),
                    indicator_name="test_indicator",
                    status="active"
                )
                await self.mqtt.publish_warning(test_warning)
                results["mqtt"] = True
                logger.info("MQTT channel test: SUCCESS")
            except Exception as e:
                logger.error(f"MQTT channel test failed: {e}")

        # Test email
        if self.email:
            results["email"] = self.email.test_connection()
            logger.info(f"Email channel test: {'SUCCESS' if results['email'] else 'FAILED'}")

        # Test SMS
        if self.sms:
            results["sms"] = self.sms.test_connection()
            logger.info(f"SMS channel test: {'SUCCESS' if results['sms'] else 'FAILED'}")

        return results

    def update_recipients(
        self,
        email_recipients: Optional[Dict[str, List[str]]] = None,
        sms_recipients: Optional[Dict[str, List[str]]] = None
    ):
        """
        Update recipient lists at runtime

        Args:
            email_recipients: New email recipient dict
            sms_recipients: New SMS recipient dict
        """
        if email_recipients is not None:
            self.email_recipients = email_recipients
            logger.info(f"Email recipients updated: {sum(len(v) for v in email_recipients.values())} total")

        if sms_recipients is not None:
            self.sms_recipients = sms_recipients
            logger.info(f"SMS recipients updated: {sum(len(v) for v in sms_recipients.values())} total")

    async def shutdown(self):
        """Shutdown all notification channels"""
        if self.mqtt:
            await self.mqtt.disconnect()

        if self.email:
            self.email.shutdown()

        if self.sms:
            self.sms.shutdown()

        logger.info("NotificationRouter shut down")
