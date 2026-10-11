"""
Mock / Virtual K-Line Adapter for Yamaha ECU testing and simulation.
Emulates Yamaha Mio GT 2015 ECU (54P-H591A) behavior, responding to Y-DIS commands,
streaming realistic RPS/RPM telemetry, and simulating DTC fault codes.
"""

import time
import math
import random
from typing import List, Optional
from .interface import KLineInterface
from ..protocol.constants import (
    YDIS_CMD_INIT,
    YDIS_CMD_READ_LIVE_DATA,
    YDIS_CMD_READ_DTC,
    YDIS_CMD_CLEAR_DTC,
    YDIS_CMD_READ_DIAG_ITEM,
    YDIS_CMD_READ_MAP_CALIBRATION,
    YDIS_CMD_SET_CO_TRIM,
)
from ..protocol.packet import calculate_checksum


class MockKLineAdapter(KLineInterface):
    """
    Virtual ECU Emulator for Yamaha Mio GT 2015 (54P / 2BJ).
    Useful for testing code, building GUI, and development without physical motorcycle.
    """

    def __init__(self, simulate_dtc_codes: Optional[List[int]] = None):
        self._connected = False
        self._buffer = bytearray()
        self.co_trim: int = 2
        self.active_dtcs: List[int] = simulate_dtc_codes if simulate_dtc_codes is not None else [15, 24]
        self.history_dtcs: List[int] = [46]
        self.start_time = time.time()
        self.simulated_rpm = 1450
        self.simulated_tps = 0.0

    def connect(self) -> bool:
        self._connected = True
        self._buffer.clear()
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._buffer.clear()

    def is_connected(self) -> bool:
        return self._connected

    def send_break_pulse(self, duration_ms: int = 25) -> None:
        # Simulate Fast Init delay
        time.sleep(duration_ms / 1000.0)

    def write(self, data: bytes) -> int:
        if not self._connected:
            return 0

        # Process the incoming packet and generate response in buffer
        response = self._process_request(data)
        if response:
            self._buffer.extend(response)
        return len(data)

    def read(self, size: int = 1, timeout_ms: int = 1000) -> bytes:
        if not self._connected or not self._buffer:
            return b""
        chunk = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return bytes(chunk)

    def read_until(self, expected_len: int, timeout_ms: int = 1500) -> bytes:
        if not self._connected:
            return b""
        deadline = time.time() + (timeout_ms / 1000.0)
        while len(self._buffer) < expected_len and time.time() < deadline:
            time.sleep(0.005)

        chunk = self._buffer[:expected_len]
        self._buffer = self._buffer[expected_len:]
        return bytes(chunk)

    def flush(self) -> None:
        self._buffer.clear()

    def _process_request(self, data: bytes) -> bytes:
        """Parse received request and formulate simulated Yamaha ECU response."""
        if len(data) < 3:
            return b""

        # Check frame structure: [HEADER: 0x12] [LENGTH] [COMMAND] ... [CHECKSUM]
        header = data[0]
        if header != 0x12:
            return b""

        length = data[1]
        cmd = data[2]

        # 1. Fast Init / Handshake (0x81 or 0x01)
        if cmd == YDIS_CMD_INIT:
            # Positive response: 0x80 [LEN] [0xC1] [ECU_ID: 54P] [CHECKSUM]
            payload = bytes([0xC1, 0x54, 0x50]) # 'TP' ~ 54P
            return self._build_response(0x80, payload)

        # 2. Live Data / RPS Telemetry (0x21)
        elif cmd == YDIS_CMD_READ_LIVE_DATA:
            elapsed = time.time() - self.start_time
            # Dynamic simulated RPM variation (idle with rev pulses)
            rev_pulse = max(0.0, math.sin(elapsed * 0.8)) * 3500.0
            rpm = int(1450 + (math.sin(elapsed * 3.0) * 80) + rev_pulse)
            rpm = max(1300, min(9500, rpm))

            tps_pct = min(100.0, (rev_pulse / 3500.0) * 45.0)
            tps_raw = int((tps_pct / 100.0) * 255)

            # Engine temp slowly warming from 65°C to 88°C
            eng_temp = min(88, int(65 + (elapsed * 0.2)))
            eng_temp_raw = eng_temp + 40

            iat_temp = 32
            iat_temp_raw = iat_temp + 40

            # MAP pressure (idle ~ 40 kPa, WOT ~ 98 kPa)
            map_kpa = int(40 + (tps_pct * 0.58))
            baro_kpa = 101

            # Battery: 14.1V (141)
            vbat_raw = 141

            # O2 sensor oscillating 0.1V - 0.9V
            o2_raw = int(128 + math.sin(elapsed * 5.0) * 110)

            # Injector duration (e.g. 2.4ms = 240 ticks)
            inj_raw = int(220 + (tps_pct * 12))

            # Ignition advance: ~10° idle up to 34°
            ign_deg = int(10 + (rpm / 9500.0) * 24)
            ign_raw = ign_deg + 10

            isc_steps = 35
            flags = 0x01 # Neutral

            payload = bytearray([
                0x61,                   # Positive response to 0x21
                (rpm >> 8) & 0xFF,
                rpm & 0xFF,
                tps_raw,
                eng_temp_raw,
                iat_temp_raw,
                map_kpa,
                baro_kpa,
                vbat_raw,
                o2_raw,
                (inj_raw >> 8) & 0xFF,
                inj_raw & 0xFF,
                ign_raw,
                isc_steps,
                flags,
            ])
            return self._build_response(0x80, bytes(payload))

        # 3. Read DTC Faults (0x13 or 0x18)
        elif cmd == YDIS_CMD_READ_DTC:
            # Payload: 0x53 [Active Count] [DTC1] [DTC2]... [History Count] [DTC_H1]...
            payload = bytearray([0x53, len(self.active_dtcs)])
            for c in self.active_dtcs:
                payload.append(c)
            payload.append(len(self.history_dtcs))
            for h in self.history_dtcs:
                payload.append(h)
            return self._build_response(0x80, bytes(payload))

        # 4. Clear DTC Faults (0x14)
        elif cmd == YDIS_CMD_CLEAR_DTC:
            self.active_dtcs.clear()
            self.history_dtcs.clear()
            payload = bytes([0x54, 0x00]) # Successfully cleared
            return self._build_response(0x80, payload)

        # 5. Read DIAG Mode (0x22, sub-item)
        elif cmd == YDIS_CMD_READ_DIAG_ITEM:
            diag_item = data[3] if len(data) > 3 else 1
            # Return item specific value
            val = 0
            if diag_item == 1: # d01: TPS angle
                val = 16 # Closed angle 16
            elif diag_item == 3: # d03: MAP
                val = 101 # kPa
            elif diag_item == 8: # d08: Lean angle
                val = 14 # 1.4V
            elif diag_item == 9: # d09: Battery
                val = 124 # 12.4V
            elif diag_item == 60: # d60: EEPROM
                val = 0
            elif diag_item == 61: # d61: Malfunction history
                val = self.history_dtcs[0] if self.history_dtcs else 0
            payload = bytes([0x62, diag_item, val])
            return self._build_response(0x80, payload)

        # 6. Read Mapping / Calibration (0x23)
        elif cmd == YDIS_CMD_READ_MAP_CALIBRATION:
            # Return basic calibration header & CO trim
            # [0x63] [CO_TRIM (offset 128)] [RPM_LIMIT_HI] [RPM_LIMIT_LO]
            rpm_limit = 9500
            payload = bytes([
                0x63,
                (self.co_trim + 128) & 0xFF,
                (rpm_limit >> 8) & 0xFF,
                rpm_limit & 0xFF,
            ])
            return self._build_response(0x80, payload)

        # 7. Set CO Trim (0x24)
        elif cmd == YDIS_CMD_SET_CO_TRIM:
            raw_co = data[3] if len(data) > 3 else 128
            self.co_trim = raw_co - 128
            payload = bytes([0x64, raw_co])
            return self._build_response(0x80, payload)

        return b""

    def _build_response(self, header: int, payload: bytes) -> bytes:
        """Formulate complete frame with length and checksum."""
        length = len(payload) + 1 # payload + checksum
        frame_without_cs = bytes([header, length]) + payload
        cs = calculate_checksum(frame_without_cs)
        return frame_without_cs + bytes([cs])
