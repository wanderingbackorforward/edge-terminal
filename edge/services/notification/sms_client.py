"""
SMS Notification Client
Sends SMS alerts for critical warning events
Implements Feature 003 - Real-Time Warning System (FR-012)
"""
import logging
from typing import List, Optional
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from edge.models.warning_event import WarningEvent

logger = logging.getLogger(__name__)


class SMSClient:
    """
    Send SMS notifications for critical warning events

    Supports multiple SMS gateways:
    - Twilio (recommended)
    - Generic HTTP API gateway
    - Serial GSM modem (for offline/remote sites)
    """

    def __init__(
        self,
        provider: str = "twilio",
        **kwargs
    ):
        """
        Initialize SMS client

        Args:
            provider: SMS gateway provider ('twilio', 'http', 'gsm')
            **kwargs: Provider-specific configuration

        Twilio kwargs:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Twilio phone number (e.g., '+1234567890')

        HTTP kwargs:
            api_url: HTTP API endpoint
            api_key: API authentication key
            from_number: Sender phone number

        GSM kwargs:
            serial_port: Serial port for GSM modem (e.g., '/dev/ttyUSB0')
            baud_rate: Baud rate (default: 115200)
        """
        self.provider = provider
        self.config = kwargs

        # Thread pool for async SMS sending
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="sms-client")

        # Initialize provider-specific client
        if provider == "twilio":
            self._init_twilio()
        elif provider == "http":
            self._init_http()
        elif provider == "gsm":
            self._init_gsm()
        else:
            raise ValueError(f"Unsupported SMS provider: {provider}")

        logger.info(f"SMSClient initialized with provider: {provider}")

    def _init_twilio(self):
        """Initialize Twilio client"""
        try:
            from twilio.rest import Client

            account_sid = self.config.get("account_sid")
            auth_token = self.config.get("auth_token")
            from_number = self.config.get("from_number")

            if not all([account_sid, auth_token, from_number]):
                raise ValueError(
                    "Twilio requires: account_sid, auth_token, from_number"
                )

            self.client = Client(account_sid, auth_token)
            self.from_number = from_number
            self.twilio_available = True
            logger.info(f"Twilio client initialized: {from_number}")

        except ImportError:
            logger.warning(
                "Twilio SDK not installed. Install with: pip install twilio"
            )
            self.twilio_available = False
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            self.twilio_available = False

    def _init_http(self):
        """Initialize HTTP API gateway client"""
        import aiohttp

        self.api_url = self.config.get("api_url")
        self.api_key = self.config.get("api_key")
        self.from_number = self.config.get("from_number")

        if not all([self.api_url, self.api_key]):
            raise ValueError("HTTP provider requires: api_url, api_key")

        self.session = None  # Created on-demand
        logger.info(f"HTTP SMS gateway initialized: {self.api_url}")

    def _init_gsm(self):
        """Initialize GSM modem"""
        try:
            import serial

            serial_port = self.config.get("serial_port", "/dev/ttyUSB0")
            baud_rate = self.config.get("baud_rate", 115200)

            self.serial_port = serial_port
            self.baud_rate = baud_rate
            self.gsm_available = True
            logger.info(f"GSM modem initialized: {serial_port} @ {baud_rate} baud")

        except ImportError:
            logger.warning(
                "PySerial not installed. Install with: pip install pyserial"
            )
            self.gsm_available = False
        except Exception as e:
            logger.error(f"Failed to initialize GSM modem: {e}")
            self.gsm_available = False

    def send_warning(
        self,
        warning: WarningEvent,
        to_numbers: List[str]
    ) -> int:
        """
        Send SMS notification for a warning event (blocking)

        Args:
            warning: Warning event to notify about
            to_numbers: List of recipient phone numbers (E.164 format: +1234567890)

        Returns:
            Number of successful sends
        """
        if not to_numbers:
            return 0

        message = self._build_message(warning)
        success_count = 0

        for number in to_numbers:
            try:
                if self.provider == "twilio":
                    self._send_twilio(number, message)
                elif self.provider == "http":
                    self._send_http(number, message)
                elif self.provider == "gsm":
                    self._send_gsm(number, message)

                success_count += 1
                logger.info(
                    f"SMS sent for warning {warning.warning_id} to {number}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to send SMS to {number} for warning {warning.warning_id}: {e}",
                    exc_info=True
                )

        return success_count

    async def send_warning_async(
        self,
        warning: WarningEvent,
        to_numbers: List[str]
    ) -> int:
        """
        Send SMS notification asynchronously (non-blocking)

        Args:
            warning: Warning event to notify about
            to_numbers: List of recipient phone numbers

        Returns:
            Number of successful sends
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.send_warning,
            warning,
            to_numbers
        )

    def _send_twilio(self, to_number: str, message: str):
        """Send SMS via Twilio"""
        if not self.twilio_available:
            raise RuntimeError("Twilio client not available")

        result = self.client.messages.create(
            body=message,
            from_=self.from_number,
            to=to_number
        )

        logger.debug(f"Twilio message SID: {result.sid}, status: {result.status}")

    def _send_http(self, to_number: str, message: str):
        """Send SMS via HTTP API gateway"""
        import requests

        payload = {
            "to": to_number,
            "from": self.from_number,
            "message": message
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            self.api_url,
            json=payload,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()
        logger.debug(f"HTTP SMS API response: {response.status_code}")

    def _send_gsm(self, to_number: str, message: str):
        """Send SMS via GSM modem using AT commands"""
        if not self.gsm_available:
            raise RuntimeError("GSM modem not available")

        import serial

        with serial.Serial(
            self.serial_port,
            self.baud_rate,
            timeout=10
        ) as ser:
            # Set SMS text mode
            ser.write(b'AT+CMGF=1\r')
            ser.readline()

            # Set recipient
            ser.write(f'AT+CMGS="{to_number}"\r'.encode())
            ser.readline()

            # Send message body
            ser.write(message.encode() + b'\x1A')  # Ctrl+Z to send

            # Wait for response
            response = ser.read(100)
            if b'OK' not in response and b'+CMGS' not in response:
                raise RuntimeError(f"GSM modem send failed: {response.decode()}")

            logger.debug(f"GSM modem response: {response.decode()}")

    def _build_message(self, warning: WarningEvent) -> str:
        """
        Build SMS message text (max 160 chars for single SMS)

        Format: [LEVEL] Ring NNN: indicator @ value (threshold)
        Example: [ALARM] Ring 350: settlement @ 35.2mm (30mm)
        """
        # Truncate indicator name if too long
        indicator_short = warning.indicator_name[:20]

        # Build message
        if warning.indicator_value is not None and warning.threshold_value is not None:
            msg = (
                f"[{warning.warning_level}] "
                f"Ring {warning.ring_number}: "
                f"{indicator_short} @ "
                f"{warning.indicator_value:.1f}{warning.indicator_unit or ''} "
                f"({warning.threshold_value:.1f})"
            )
        elif warning.predicted_value is not None:
            msg = (
                f"[{warning.warning_level}] "
                f"Ring {warning.ring_number}: "
                f"{indicator_short} predicted "
                f"{warning.predicted_value:.1f}{warning.indicator_unit or ''}"
            )
        else:
            msg = (
                f"[{warning.warning_level}] "
                f"Ring {warning.ring_number}: "
                f"{indicator_short}"
            )

        # Ensure message fits in single SMS (160 chars)
        if len(msg) > 160:
            msg = msg[:157] + "..."

        return msg

    def test_connection(self, test_number: Optional[str] = None) -> bool:
        """
        Test SMS gateway connection

        Args:
            test_number: Optional phone number to send test SMS to

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.provider == "twilio":
                if not self.twilio_available:
                    return False

                # Test Twilio API access
                account = self.client.api.accounts(self.config.get("account_sid")).fetch()
                logger.info(f"Twilio account test successful: {account.friendly_name}")

                if test_number:
                    self._send_twilio(test_number, "Shield Tunneling SMS test message")
                    logger.info(f"Test SMS sent to {test_number}")

                return True

            elif self.provider == "http":
                # Test HTTP API endpoint
                import requests
                response = requests.get(
                    self.api_url.rsplit('/', 1)[0] + "/health",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=5
                )
                logger.info(f"HTTP API test: {response.status_code}")
                return response.status_code < 400

            elif self.provider == "gsm":
                if not self.gsm_available:
                    return False

                # Test GSM modem connection
                import serial
                with serial.Serial(self.serial_port, self.baud_rate, timeout=5) as ser:
                    ser.write(b'AT\r')
                    response = ser.readline()
                    if b'OK' in response:
                        logger.info("GSM modem test successful")
                        return True
                    else:
                        logger.warning(f"GSM modem test failed: {response.decode()}")
                        return False

            return False

        except Exception as e:
            logger.error(f"SMS connection test failed: {e}", exc_info=True)
            return False

    def shutdown(self):
        """Shutdown thread pool and close connections"""
        self.executor.shutdown(wait=True)

        if self.provider == "http" and self.session:
            # Close aiohttp session if exists
            pass

        logger.info("SMSClient shut down")
