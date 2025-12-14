"""
Warning System Configuration Loader
Loads and parses warnings.yaml configuration file
Implements Feature 003 - Real-Time Warning System
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MQTTConfig:
    """MQTT broker configuration"""
    broker_host: str = "localhost"
    broker_port: int = 1883
    client_id: str = "edge-warning-publisher"
    username: Optional[str] = None
    password: Optional[str] = None
    qos: int = 1
    retain: bool = True
    topics: Dict[str, str] = field(default_factory=dict)


@dataclass
class EmailConfig:
    """Email notification configuration"""
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_address: str = ""
    from_name: str = "Shield Tunneling Alert System"
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30
    recipients: Dict[str, list] = field(default_factory=dict)


@dataclass
class SMSConfig:
    """SMS notification configuration"""
    enabled: bool = False
    provider: str = "twilio"  # twilio, http, gsm
    twilio: Dict[str, str] = field(default_factory=dict)
    http: Dict[str, str] = field(default_factory=dict)
    gsm: Dict[str, Any] = field(default_factory=dict)
    recipients: Dict[str, list] = field(default_factory=dict)


@dataclass
class RetryConfig:
    """Notification retry configuration"""
    enabled: bool = True
    max_attempts: int = 3
    max_task_age_hours: int = 24
    cleanup_interval_seconds: int = 3600
    backoff_delays: list = field(default_factory=lambda: [60, 300, 900])


@dataclass
class WarningConfig:
    """Complete warning system configuration"""
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    sms: SMSConfig = field(default_factory=SMSConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    graded_response: Dict[str, Dict] = field(default_factory=dict)
    batching: Dict[str, Any] = field(default_factory=dict)
    logging: Dict[str, Any] = field(default_factory=dict)


class WarningConfigLoader:
    """
    Load warning system configuration from YAML file

    Usage:
        loader = WarningConfigLoader()
        config = loader.load("edge/config/warnings.yaml")

        # Access configuration
        print(config.mqtt.broker_host)
        print(config.email.recipients["ALARM"])
    """

    @staticmethod
    def load(config_path: str = "edge/config/warnings.yaml") -> WarningConfig:
        """
        Load configuration from YAML file

        Args:
            config_path: Path to warnings.yaml file

        Returns:
            WarningConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        path = Path(config_path)

        if not path.exists():
            logger.warning(
                f"Warning config file not found: {config_path}, "
                f"using default configuration"
            )
            return WarningConfig()

        try:
            with open(path, 'r') as f:
                raw_config = yaml.safe_load(f)

            if not raw_config:
                logger.warning("Empty config file, using defaults")
                return WarningConfig()

            # Parse configuration sections
            config = WarningConfig()

            # MQTT configuration
            if "mqtt" in raw_config:
                mqtt_data = raw_config["mqtt"]
                config.mqtt = MQTTConfig(
                    broker_host=mqtt_data.get("broker_host", "localhost"),
                    broker_port=mqtt_data.get("broker_port", 1883),
                    client_id=mqtt_data.get("client_id", "edge-warning-publisher"),
                    username=mqtt_data.get("username"),
                    password=mqtt_data.get("password"),
                    qos=mqtt_data.get("qos", 1),
                    retain=mqtt_data.get("retain", True),
                    topics=mqtt_data.get("topics", {})
                )

            # Email configuration
            if "email" in raw_config:
                email_data = raw_config["email"]
                config.email = EmailConfig(
                    enabled=email_data.get("enabled", False),
                    smtp_host=email_data.get("smtp_host", ""),
                    smtp_port=email_data.get("smtp_port", 587),
                    smtp_user=email_data.get("smtp_user", ""),
                    smtp_password=email_data.get("smtp_password", ""),
                    from_address=email_data.get("from_address", ""),
                    from_name=email_data.get("from_name", "Shield Tunneling Alert System"),
                    use_tls=email_data.get("use_tls", True),
                    use_ssl=email_data.get("use_ssl", False),
                    timeout=email_data.get("timeout", 30),
                    recipients=email_data.get("recipients", {})
                )

            # SMS configuration
            if "sms" in raw_config:
                sms_data = raw_config["sms"]
                config.sms = SMSConfig(
                    enabled=sms_data.get("enabled", False),
                    provider=sms_data.get("provider", "twilio"),
                    twilio=sms_data.get("twilio", {}),
                    http=sms_data.get("http", {}),
                    gsm=sms_data.get("gsm", {}),
                    recipients=sms_data.get("recipients", {})
                )

            # Retry configuration
            if "retry" in raw_config:
                retry_data = raw_config["retry"]
                config.retry = RetryConfig(
                    enabled=retry_data.get("enabled", True),
                    max_attempts=retry_data.get("max_attempts", 3),
                    max_task_age_hours=retry_data.get("max_task_age_hours", 24),
                    cleanup_interval_seconds=retry_data.get("cleanup_interval_seconds", 3600),
                    backoff_delays=retry_data.get("backoff_delays", [60, 300, 900])
                )

            # Graded response configuration
            config.graded_response = raw_config.get("graded_response", {})

            # Batching configuration
            config.batching = raw_config.get("batching", {})

            # Logging configuration
            config.logging = raw_config.get("logging", {})

            logger.info(f"Warning configuration loaded from {config_path}")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse config file {config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load config file {config_path}: {e}")
            raise

    @staticmethod
    def validate(config: WarningConfig) -> tuple[bool, list]:
        """
        Validate configuration

        Args:
            config: WarningConfig to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate MQTT
        if not config.mqtt.broker_host:
            errors.append("MQTT broker_host is required")
        if not (1 <= config.mqtt.broker_port <= 65535):
            errors.append(f"Invalid MQTT port: {config.mqtt.broker_port}")

        # Validate Email if enabled
        if config.email.enabled:
            if not config.email.smtp_host:
                errors.append("Email SMTP host is required when email is enabled")
            if not config.email.from_address:
                errors.append("Email from_address is required when email is enabled")
            if not config.email.recipients:
                errors.append("Email recipients list is empty")

        # Validate SMS if enabled
        if config.sms.enabled:
            if config.sms.provider == "twilio":
                if not config.sms.twilio.get("account_sid"):
                    errors.append("Twilio account_sid is required")
                if not config.sms.twilio.get("auth_token"):
                    errors.append("Twilio auth_token is required")
                if not config.sms.twilio.get("from_number"):
                    errors.append("Twilio from_number is required")
            elif config.sms.provider == "http":
                if not config.sms.http.get("api_url"):
                    errors.append("HTTP API URL is required")
            elif config.sms.provider == "gsm":
                if not config.sms.gsm.get("serial_port"):
                    errors.append("GSM serial_port is required")

            if not config.sms.recipients:
                errors.append("SMS recipients list is empty")

        # Validate retry configuration
        if config.retry.max_attempts < 1:
            errors.append("Retry max_attempts must be >= 1")
        if config.retry.max_task_age_hours < 1:
            errors.append("Retry max_task_age_hours must be >= 1")

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def save(config: WarningConfig, config_path: str = "edge/config/warnings.yaml"):
        """
        Save configuration to YAML file

        Args:
            config: WarningConfig to save
            config_path: Path to save to
        """
        # Convert dataclasses to dicts
        config_dict = {
            "mqtt": {
                "broker_host": config.mqtt.broker_host,
                "broker_port": config.mqtt.broker_port,
                "client_id": config.mqtt.client_id,
                "username": config.mqtt.username,
                "password": config.mqtt.password,
                "qos": config.mqtt.qos,
                "retain": config.mqtt.retain,
                "topics": config.mqtt.topics
            },
            "email": {
                "enabled": config.email.enabled,
                "smtp_host": config.email.smtp_host,
                "smtp_port": config.email.smtp_port,
                "smtp_user": config.email.smtp_user,
                "smtp_password": config.email.smtp_password,
                "from_address": config.email.from_address,
                "from_name": config.email.from_name,
                "use_tls": config.email.use_tls,
                "use_ssl": config.email.use_ssl,
                "timeout": config.email.timeout,
                "recipients": config.email.recipients
            },
            "sms": {
                "enabled": config.sms.enabled,
                "provider": config.sms.provider,
                "twilio": config.sms.twilio,
                "http": config.sms.http,
                "gsm": config.sms.gsm,
                "recipients": config.sms.recipients
            },
            "retry": {
                "enabled": config.retry.enabled,
                "max_attempts": config.retry.max_attempts,
                "max_task_age_hours": config.retry.max_task_age_hours,
                "cleanup_interval_seconds": config.retry.cleanup_interval_seconds,
                "backoff_delays": config.retry.backoff_delays
            },
            "graded_response": config.graded_response,
            "batching": config.batching,
            "logging": config.logging
        }

        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Warning configuration saved to {config_path}")
