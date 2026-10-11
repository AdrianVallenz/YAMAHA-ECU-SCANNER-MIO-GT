"""
Custom exceptions for Yamaha ECU communication and diagnostic framework.
"""

class YamahaECUException(Exception):
    """Base exception for all Yamaha ECU operations."""
    pass


class HardwareConnectionError(YamahaECUException):
    """Raised when hardware adapter (K-Line/Serial) fails to connect."""
    pass


class ProtocolTimeoutError(YamahaECUException):
    """Raised when ECU fails to respond within the expected timeout period."""
    pass


class ChecksumError(YamahaECUException):
    """Raised when a received frame has an invalid checksum."""
    pass


class InvalidResponseError(YamahaECUException):
    """Raised when ECU returns an unrecognized or malformed response frame."""
    pass


class SecurityAccessDeniedError(YamahaECUException):
    """Raised when ECU rejects access to protected memory/diagnostic routines."""
    pass


class MappingReadError(YamahaECUException):
    """Raised when reading mapping tables or EEPROM fails."""
    pass
