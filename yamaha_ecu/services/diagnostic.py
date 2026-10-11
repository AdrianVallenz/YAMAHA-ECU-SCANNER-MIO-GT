"""
Diagnostic Service for Yamaha Mio GT 2015.
Provides high-level functions to:
- Read active and historical Diagnostic Trouble Codes (DTC).
- Clear fault code memories.
- Read DIAG mode items (d01 to d70: TPS, MAP, Battery, Lean Angle, etc.).
- Trigger actuator output tests (Ignition coil spark, Injector test).
"""

from typing import List, Dict, Any, Tuple
from ..protocol.ydis import YDISProtocol
from ..protocol.constants import (
    YDIS_CMD_READ_DTC,
    YDIS_CMD_CLEAR_DTC,
    YDIS_CMD_READ_DIAG_ITEM,
    YDIS_CMD_ACTUATOR_TEST,
    DIAG_ITEMS,
)
from ..models.dtc import DTCFault, lookup_dtc


class DiagnosticService:
    """Service to handle Yamaha ECU Diagnostics (DTC & DIAG Mode)."""

    def __init__(self, protocol: YDISProtocol):
        self.protocol = protocol

    def read_dtc(self) -> Tuple[List[DTCFault], List[DTCFault]]:
        """
        Reads active and history fault codes from Yamaha ECU.
        Returns:
            (active_faults_list, history_faults_list)
        """
        resp_id, payload = self.protocol.send_command(YDIS_CMD_READ_DTC)
        # Expected payload format:
        # [0x53 (Echo cmd)] [Active Count] [Code1, Code2...] [Hist Count] [HCode1...]
        active_faults: List[DTCFault] = []
        history_faults: List[DTCFault] = []

        if len(payload) >= 1:
            idx = 0
            if payload[0] == 0x53:
                idx = 1

            # Active codes
            if idx < len(payload):
                active_count = payload[idx]
                idx += 1
                for _ in range(active_count):
                    if idx < len(payload):
                        code = payload[idx]
                        active_faults.append(lookup_dtc(code, is_active=True))
                        idx += 1

            # History codes
            if idx < len(payload):
                history_count = payload[idx]
                idx += 1
                for _ in range(history_count):
                    if idx < len(payload):
                        code = payload[idx]
                        history_faults.append(lookup_dtc(code, is_active=False))
                        idx += 1

        return active_faults, history_faults

    def clear_dtc(self) -> bool:
        """
        Clears stored historical and active malfunction codes in ECU EEPROM memory.
        """
        resp_id, payload = self.protocol.send_command(YDIS_CMD_CLEAR_DTC)
        # Response 0x54 indicates positive response to command 0x14 (0x14 + 0x40)
        return resp_id in (0x54, 0x80) or (len(payload) > 0 and payload[0] == 0x54)

    def read_diag_item(self, item_number: int) -> Dict[str, Any]:
        """
        Reads a specific DIAG mode code (e.g., d01=TPS angle, d09=Battery Voltage).
        """
        payload_req = bytes([item_number])
        resp_id, payload = self.protocol.send_command(YDIS_CMD_READ_DIAG_ITEM, payload_req)

        meta = DIAG_ITEMS.get(item_number, {
            "name": f"d{item_number:02d}: Custom Diagnostic Item",
            "unit": "raw",
            "min": 0,
            "max": 255,
        })

        raw_val = payload[1] if len(payload) > 1 else (payload[0] if payload else 0)

        # Value engineering conversions
        display_val = raw_val
        if item_number == 9:  # Battery (d09): x 0.1 V
            display_val = round(raw_val * 0.1, 2)
        elif item_number == 8: # Lean angle (d08): x 0.1 V
            display_val = round(raw_val * 0.1, 2)

        return {
            "code": item_number,
            "name": meta["name"],
            "raw_value": raw_val,
            "value": display_val,
            "unit": meta["unit"],
            "in_range": meta["min"] <= raw_val <= meta["max"],
        }

    def run_all_sensor_diagnostics(self) -> List[Dict[str, Any]]:
        """
        Queries all primary diagnostic sensors (d01, d03, d05, d08, d09, d60).
        """
        results = []
        for code in [1, 3, 5, 8, 9, 60, 61]:
            try:
                res = self.read_diag_item(code)
                results.append(res)
            except Exception:
                continue
        return results

    def trigger_actuator_test(self, test_code: int) -> bool:
        """
        Triggers active test routines (e.g. d30: spark ignition 5 times, d36: injector click 5 times).
        """
        payload_req = bytes([test_code, 0x01])
        resp_id, payload = self.protocol.send_command(YDIS_CMD_ACTUATOR_TEST, payload_req)
        return True
