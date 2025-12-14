"""
T062: Centralized Error Handling
Custom exceptions and error handling utilities
"""
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Standard error codes for the application"""
    # Database errors (1xxx)
    DATABASE_CONNECTION_ERROR = 1001
    DATABASE_QUERY_ERROR = 1002
    DATABASE_TRANSACTION_ERROR = 1003

    # Data collection errors (2xxx)
    OPCUA_CONNECTION_ERROR = 2001
    MODBUS_CONNECTION_ERROR = 2002
    DATA_SOURCE_ERROR = 2003

    # Data quality errors (3xxx)
    VALIDATION_ERROR = 3001
    CALIBRATION_ERROR = 3002
    INTERPOLATION_ERROR = 3003

    # Alignment errors (4xxx)
    RING_DETECTION_ERROR = 4001
    AGGREGATION_ERROR = 4002
    FEATURE_CALCULATION_ERROR = 4003

    # API errors (5xxx)
    INVALID_REQUEST = 5001
    RESOURCE_NOT_FOUND = 5002
    UNAUTHORIZED = 5003

    # System errors (9xxx)
    CONFIGURATION_ERROR = 9001
    UNKNOWN_ERROR = 9999


class EdgeServiceError(Exception):
    """
    Base exception for edge service errors.

    All custom exceptions should inherit from this class.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[ErrorCode] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize exception.

        Args:
            message: Error message
            error_code: Error code enum
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or ErrorCode.UNKNOWN_ERROR
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code.value,
            'error_name': self.error_code.name,
            'details': self.details
        }


# Database exceptions
class DatabaseError(EdgeServiceError):
    """Database operation error"""
    pass


class DatabaseConnectionError(DatabaseError):
    """Database connection error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.DATABASE_CONNECTION_ERROR, details)


class DatabaseQueryError(DatabaseError):
    """Database query error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.DATABASE_QUERY_ERROR, details)


# Data collection exceptions
class DataCollectionError(EdgeServiceError):
    """Data collection error"""
    pass


class OPCUAConnectionError(DataCollectionError):
    """OPC UA connection error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.OPCUA_CONNECTION_ERROR, details)


class ModbusConnectionError(DataCollectionError):
    """Modbus TCP connection error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.MODBUS_CONNECTION_ERROR, details)


# Data quality exceptions
class DataQualityError(EdgeServiceError):
    """Data quality error"""
    pass


class ValidationError(DataQualityError):
    """Data validation error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.VALIDATION_ERROR, details)


# Alignment exceptions
class AlignmentError(EdgeServiceError):
    """Data alignment error"""
    pass


class RingDetectionError(AlignmentError):
    """Ring boundary detection error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.RING_DETECTION_ERROR, details)


class AggregationError(AlignmentError):
    """Data aggregation error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.AGGREGATION_ERROR, details)


# API exceptions
class APIError(EdgeServiceError):
    """API error"""
    pass


class InvalidRequestError(APIError):
    """Invalid request error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.INVALID_REQUEST, details)


class ResourceNotFoundError(APIError):
    """Resource not found error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.RESOURCE_NOT_FOUND, details)


# Configuration exception
class ConfigurationError(EdgeServiceError):
    """Configuration error"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, ErrorCode.CONFIGURATION_ERROR, details)


# Error handler decorator
def handle_errors(
    default_return=None,
    log_error: bool = True,
    raise_on_error: bool = False
):
    """
    Decorator for error handling.

    Args:
        default_return: Default return value on error
        log_error: Whether to log errors
        raise_on_error: Whether to re-raise exceptions

    Example:
        @handle_errors(default_return=[], log_error=True)
        def risky_function():
            # Function that might raise exceptions
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except EdgeServiceError as e:
                if log_error:
                    logger.error(
                        f"Error in {func.__name__}: {e.message}",
                        extra={'error_code': e.error_code.name, 'details': e.details}
                    )
                if raise_on_error:
                    raise
                return default_return
            except Exception as e:
                if log_error:
                    logger.exception(f"Unexpected error in {func.__name__}: {e}")
                if raise_on_error:
                    raise
                return default_return
        return wrapper
    return decorator


# Async error handler decorator
def handle_errors_async(
    default_return=None,
    log_error: bool = True,
    raise_on_error: bool = False
):
    """
    Decorator for async error handling.

    Example:
        @handle_errors_async(default_return=[], log_error=True)
        async def risky_async_function():
            # Async function that might raise exceptions
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except EdgeServiceError as e:
                if log_error:
                    logger.error(
                        f"Error in {func.__name__}: {e.message}",
                        extra={'error_code': e.error_code.name, 'details': e.details}
                    )
                if raise_on_error:
                    raise
                return default_return
            except Exception as e:
                if log_error:
                    logger.exception(f"Unexpected error in {func.__name__}: {e}")
                if raise_on_error:
                    raise
                return default_return
        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example 1: Raise and catch custom exception
    try:
        raise DatabaseConnectionError(
            "Failed to connect to database",
            details={'host': 'localhost', 'port': 5432}
        )
    except EdgeServiceError as e:
        print(f"Caught exception: {e.to_dict()}")

    # Example 2: Using decorator
    @handle_errors(default_return=0, log_error=True)
    def divide(a, b):
        if b == 0:
            raise ValidationError("Division by zero", details={'a': a, 'b': b})
        return a / b

    result = divide(10, 0)
    print(f"Result: {result}")  # Will return 0

    # Example 3: Normal operation
    result = divide(10, 2)
    print(f"Result: {result}")  # Will return 5.0
