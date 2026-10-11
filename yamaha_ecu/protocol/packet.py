"""
Yamaha ECU Protocol Packet Framing and Checksum Handling.
Handles serialization and deserialization of K-Line packets.
"""

from typing import Tuple, Optional
from .constants import YDIS_REQUEST_HEADER, YDIS_RESPONSE_HEADER, YDIS_NEGATIVE_RESPONSE
from ..core.exceptions import ChecksumError, InvalidResponseError


def calculate_checksum(data: bytes) -> int:
    """
    Standard Yamaha 8-bit additive checksum:
    Sum of all packet bytes modulo 256.
    """
    return sum(data) & 0xFF


def build_request_frame(command: int, payload: bytes = b"") -> bytes:
    """
    Constructs an outgoing request frame for Yamaha ECU.
    Format:
    [0x12 (HEADER)] [LENGTH (cmd + payload + checksum)] [COMMAND] [PAYLOAD...] [CHECKSUM]
    """
    # length includes command byte, payload bytes, and checksum byte
    length = 1 + len(payload) + 1
    frame_body = bytes([YDIS_REQUEST_HEADER, length, command]) + payload
    cs = calculate_checksum(frame_body)
    return frame_body + bytes([cs])


def parse_response_frame(raw_bytes: bytes) -> Tuple[int, bytes]:
    """
    Validates and unpacks an incoming response frame from Yamaha ECU.
    Returns:
        (command_response_id, payload_bytes)
    Raises:
        InvalidResponseError: If header or length is malformed.
        ChecksumError: If computed checksum differs from received checksum.
    """
    if len(raw_bytes) < 4:
        raise InvalidResponseError(f"Frame terlalu pendek: {len(raw_bytes)} bytes (minimal 4 bytes).")

    header = raw_bytes[0]
    if header != YDIS_RESPONSE_HEADER:
        raise InvalidResponseError(f"Header respon tidak valid: 0x{header:02X} (diharapkan 0x{YDIS_RESPONSE_HEADER:02X}).")

    length = raw_bytes[1]
    expected_total_len = 2 + length  # header + length + (payload + cs)
    if len(raw_bytes) < expected_total_len:
        raise InvalidResponseError(
            f"Ukuran frame tidak lengkap: diterima {len(raw_bytes)} bytes, dibutuhkan {expected_total_len} bytes."
        )

    # Checksum verification
    frame_body = raw_bytes[:expected_total_len - 1]
    received_cs = raw_bytes[expected_total_len - 1]
    computed_cs = calculate_checksum(frame_body)

    if received_cs != computed_cs:
        raise ChecksumError(
            f"Checksum tidak cocok! Diterima: 0x{received_cs:02X}, Dihitung: 0x{computed_cs:02X}."
        )

    resp_cmd = raw_bytes[2]
    payload = raw_bytes[3:expected_total_len - 1]

    # Negative response detection (0x7F)
    if resp_cmd == YDIS_NEGATIVE_RESPONSE:
        err_code = payload[1] if len(payload) > 1 else (payload[0] if payload else 0x00)
        raise InvalidResponseError(f"ECU mengembalikan Negative Response (NRC: 0x{err_code:02X}).")

    return resp_cmd, payload
