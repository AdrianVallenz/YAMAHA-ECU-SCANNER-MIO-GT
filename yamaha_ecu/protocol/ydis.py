"""
Yamaha Diagnostic System (Y-DIS) Protocol Layer.
Handles communication transactions, handshake sequence, and request-response round-trips.
"""

import time
from typing import Tuple, Optional
from ..hardware.interface import KLineInterface
from ..core.exceptions import ProtocolTimeoutError, HardwareConnectionError
from .packet import build_request_frame, parse_response_frame
from .constants import YDIS_CMD_INIT


class YDISProtocol:
    """
    Stateful protocol driver that sends commands to Yamaha ECU via K-Line.
    """

    def __init__(self, hardware: KLineInterface):
        self.hardware = hardware
        self.is_initialized = False

    def initialize_session(self, use_fast_init: bool = True) -> bool:
        """
        Performs handshake / wake-up sequence with Yamaha ECU.
        1. Fast Init: 25ms Break Pulse LOW followed by 25ms HIGH.
        2. Send Init Command (0x81).
        3. Await ECU positive response (0xC1).
        """
        if not self.hardware.is_connected():
            if not self.hardware.connect():
                raise HardwareConnectionError("Gagal membuka koneksi hardware K-Line.")

        if use_fast_init:
            # Send Fast-Init pulse
            self.hardware.send_break_pulse(duration_ms=25)
            time.sleep(0.025)

        self.hardware.flush()

        # Send Init handshake frame
        req = build_request_frame(YDIS_CMD_INIT)
        self.hardware.write(req)

        # Read response (typically 6-7 bytes)
        raw_resp = self._read_frame_response(timeout_ms=1200)
        if not raw_resp:
            raise ProtocolTimeoutError("Tidak ada respon dari ECU saat inisialisasi handshake.")

        resp_cmd, payload = parse_response_frame(raw_resp)
        # 0xC1 is positive response to 0x81 (0x81 + 0x40)
        if resp_cmd == 0xC1:
            self.is_initialized = True
            return True

        return False

    def send_command(self, command: int, payload: bytes = b"", timeout_ms: int = 800) -> Tuple[int, bytes]:
        """
        Sends an application command and returns (response_id, payload_bytes).
        """
        if not self.hardware.is_connected():
            raise HardwareConnectionError("Hardware belum terhubung.")

        req_frame = build_request_frame(command, payload)
        self.hardware.flush()
        self.hardware.write(req_frame)

        raw_resp = self._read_frame_response(timeout_ms=timeout_ms)
        if not raw_resp:
            raise ProtocolTimeoutError(f"Timeout menunggu respon untuk command 0x{command:02X}.")

        return parse_response_frame(raw_resp)

    def _read_frame_response(self, timeout_ms: int = 1000) -> bytes:
        """
        Reads a dynamic length frame:
        Byte 0: Header (0x80)
        Byte 1: Length (N)
        Following: N bytes (Payload + Checksum)
        """
        start = time.time()
        deadline = start + (timeout_ms / 1000.0)

        # Read Header & Length (2 bytes)
        hdr = bytearray()
        while len(hdr) < 2 and time.time() < deadline:
            b = self.hardware.read(1, timeout_ms=50)
            if b:
                # Find start header (0x80)
                if not hdr and b[0] == 0x80:
                    hdr.append(b[0])
                elif len(hdr) == 1:
                    hdr.append(b[0])

        if len(hdr) < 2:
            return b""

        length = hdr[1]
        remaining = self.hardware.read_until(length, timeout_ms=int((deadline - time.time()) * 1000))
        if len(remaining) < length:
            return b""

        return bytes(hdr + remaining)
