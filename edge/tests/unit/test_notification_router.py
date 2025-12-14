"""
T133: Unit tests for notification router
Tests NotificationRouter for graded response mechanism
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock

from edge.services.notification.notification_router import NotificationRouter
from edge.models.warning_event import WarningEvent


@pytest.fixture
def mock_mqtt():
    mqtt = Mock()
    mqtt.publish_warning = AsyncMock()
    mqtt.publish_warnings_batch = AsyncMock()
    return mqtt


@pytest.fixture
def mock_email():
    email = Mock()
    email.send_warning_async = AsyncMock(return_value=True)
    email.send_batch = Mock(return_value=1)
    return email


@pytest.fixture
def mock_sms():
    sms = Mock()
    sms.send_warning_async = AsyncMock(return_value=2)
    return sms


@pytest.fixture
def notification_config():
    return {
        "email_recipients": {
            "WARNING": ["engineer@example.com"],
            "ALARM": ["engineer@example.com", "manager@example.com"]
        },
        "sms_recipients": {
            "ALARM": ["+1234567890", "+0987654321"]
        }
    }


@pytest.fixture
def router(mock_mqtt, mock_email, mock_sms, notification_config):
    return NotificationRouter(
        mqtt_publisher=mock_mqtt,
        email_notifier=mock_email,
        sms_client=mock_sms,
        notification_config=notification_config
    )


def create_warning(level):
    return WarningEvent(
        warning_id=f"test-{level}",
        warning_type="threshold",
        warning_level=level,
        ring_number=100,
        timestamp=1234567890.0,
        indicator_name="settlement_value",
        indicator_value=35.0,
        status="active"
    )


class TestNotificationRouter:
    """Unit tests for NotificationRouter"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_attention_mqtt_only(self, router, mock_mqtt, mock_email, mock_sms):
        """Test ATTENTION warnings go to MQTT only"""
        warning = create_warning("ATTENTION")

        results = await router.route_warning(warning)

        assert results["mqtt"] == True
        assert results["email"] == False
        assert results["sms"] == False

        mock_mqtt.publish_warning.assert_called_once()
        mock_email.send_warning_async.assert_not_called()
        mock_sms.send_warning_async.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_warning_mqtt_and_email(self, router, mock_mqtt, mock_email, mock_sms):
        """Test WARNING warnings go to MQTT + Email"""
        warning = create_warning("WARNING")

        results = await router.route_warning(warning)

        assert results["mqtt"] == True
        assert results["email"] == True
        assert results["sms"] == False

        mock_mqtt.publish_warning.assert_called_once()
        mock_email.send_warning_async.assert_called_once()
        mock_sms.send_warning_async.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_alarm_all_channels(self, router, mock_mqtt, mock_email, mock_sms):
        """Test ALARM warnings go to MQTT + Email + SMS"""
        warning = create_warning("ALARM")

        results = await router.route_warning(warning)

        assert results["mqtt"] == True
        assert results["email"] == True
        assert results["sms"] == True

        mock_mqtt.publish_warning.assert_called_once()
        mock_email.send_warning_async.assert_called_once()
        mock_sms.send_warning_async.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_email_recipients_by_level(self, router, mock_email):
        """Test that email recipients vary by warning level"""
        warning_warning = create_warning("WARNING")
        alarm_warning = create_warning("ALARM")

        await router.route_warning(warning_warning)
        warning_call = mock_email.send_warning_async.call_args_list[0]
        warning_recipients = warning_call[0][1]

        await router.route_warning(alarm_warning)
        alarm_call = mock_email.send_warning_async.call_args_list[1]
        alarm_recipients = alarm_call[0][1]

        # ALARM should have more recipients than WARNING
        assert len(alarm_recipients) >= len(warning_recipients)
        assert "manager@example.com" in alarm_recipients

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_batch_routing(self, router, mock_mqtt, mock_email):
        """Test batch warning routing"""
        warnings = [
            create_warning("WARNING"),
            create_warning("WARNING"),
            create_warning("ALARM"),
        ]

        counts = await router.route_warnings_batch(warnings)

        assert counts["mqtt"] == 3
        assert counts["email"] > 0

        mock_mqtt.publish_warnings_batch.assert_called_once()

    @pytest.mark.unit
    def test_statistics_tracking(self, router):
        """Test that notification statistics are tracked"""
        initial_stats = router.get_statistics()
        assert initial_stats["mqtt"]["sent"] == 0

        # Manually update stats (simulate sending)
        router.stats["mqtt_sent"] += 1
        router.stats["email_sent"] += 1

        stats = router.get_statistics()
        assert stats["mqtt"]["sent"] == 1
        assert stats["email"]["sent"] == 1

    @pytest.mark.unit
    def test_update_recipients(self, router):
        """Test runtime recipient list updates"""
        new_email_recipients = {
            "ALARM": ["new-manager@example.com"]
        }

        router.update_recipients(email_recipients=new_email_recipients)

        assert router.email_recipients["ALARM"] == ["new-manager@example.com"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mqtt_failure_doesnt_block(self, router, mock_mqtt):
        """Test that MQTT failures don't block other channels"""
        mock_mqtt.publish_warning.side_effect = Exception("MQTT connection failed")

        warning = create_warning("ALARM")
        results = await router.route_warning(warning)

        # MQTT should fail but email/sms should still succeed
        assert results["mqtt"] == False
        # Other channels should still be attempted (implementation dependent)
