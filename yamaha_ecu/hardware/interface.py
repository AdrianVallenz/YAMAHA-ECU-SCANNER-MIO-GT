"""
Hardware abstraction layer interface for K-Line / Serial ECU communication.
"""

from abc import ABC, abstractmethod
from typing import Optional


class KLineInterface(ABC):
    """Abstract Base Class for hardware adapters interacting with ECU K-Line."""

    @abstractmethod
    def connect(self) -> bool:
        """Initialize and open the communication port."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close the communication port and reset lines."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is currently active."""
        pass

    @abstractmethod
    def send_break_pulse(self, duration_ms: int = 25) -> None:
        """Send ISO 14230 / KWP2000 Fast Init or 5-Baud initialization break pulse."""
        pass

    @abstractmethod
    def write(self, data: bytes) -> int:
        """Write raw bytes to the K-Line."""
        pass

    @abstractmethod
    def read(self, size: int = 1, timeout_ms: int = 1000) -> bytes:
        """Read specific number of bytes from the K-Line."""
        pass

    @abstractmethod
    def read_until(self, expected_len: int, timeout_ms: int = 1500) -> bytes:
        """Read until expected length is received or timeout expires."""
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush input and output hardware buffers."""
        pass
