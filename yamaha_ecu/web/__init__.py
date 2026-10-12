"""
Yamaha ECU Web Dashboard & Visual Telemetry Server.
Zero-dependency HTTP + Server-Sent Events (SSE) server for real-time visualization.
"""

from .server import start_web_server

__all__ = ["start_web_server"]
