"""
Unit and Integration Tests for Yamaha ECU Diagnostic & Mapping Framework.
Using Python standard library unittest for zero-dependency execution.
"""

import os
import json
import unittest
from yamaha_ecu import (
    YamahaECUClient,
    MockKLineAdapter,
    SensorData,
    DTCFault,
)
from yamaha_ecu.protocol.packet import calculate_checksum, build_request_frame, parse_response_frame
from yamaha_ecu.protocol.constants import YDIS_REQUEST_HEADER, YDIS_RESPONSE_HEADER, YDIS_CMD_READ_LIVE_DATA
from yamaha_ecu.models.dtc import lookup_dtc, YAMAHA_MIO_GT_DTC_MAP
from yamaha_ecu.models.map_tables import ECUMappingProfile, MapTable2D, MapTable3D
from yamaha_ecu.core.exceptions import ChecksumError, InvalidResponseError


class TestYamahaECUFramework(unittest.TestCase):

    def test_checksum_calculation(self):
        data = bytes([0x12, 0x03, 0x81])
        cs = calculate_checksum(data)
        self.assertEqual(cs, 0x96)

    def test_build_request_frame(self):
        frame = build_request_frame(YDIS_CMD_READ_LIVE_DATA)
        self.assertEqual(frame, bytes([0x12, 0x02, 0x21, 0x35]))

    def test_parse_response_frame(self):
        body = bytes([0x80, 0x03, 0x61, 0xAA])
        cs = calculate_checksum(body)
        full_frame = body + bytes([cs])

        resp_cmd, payload = parse_response_frame(full_frame)
        self.assertEqual(resp_cmd, 0x61)
        self.assertEqual(payload, bytes([0xAA]))

    def test_parse_response_checksum_mismatch(self):
        body = bytes([0x80, 0x03, 0x61, 0xAA, 0x00])
        with self.assertRaises(ChecksumError):
            parse_response_frame(body)

    def test_dtc_lookup_mio_gt(self):
        fault_tps = lookup_dtc(15, is_active=True)
        self.assertEqual(fault_tps.code, 15)
        self.assertIn("Throttle Position Sensor", fault_tps.name)
        self.assertTrue(fault_tps.is_active)

        fault_pulser = lookup_dtc(12, is_active=False)
        self.assertEqual(fault_pulser.code, 12)
        self.assertIn("Crankshaft", fault_pulser.name)
        self.assertFalse(fault_pulser.is_active)

        fault_unknown = lookup_dtc(99, is_active=True)
        self.assertEqual(fault_unknown.code, 99)
        self.assertIn("Unknown", fault_unknown.name)

    def test_sensor_data_parsing(self):
        raw = bytes([
            0x05, 0xDC,  # RPM: 1500
            128,         # TPS
            125,         # Eng Temp: 85C
            72,          # IAT: 32C
            45,          # MAP
            101,         # Baro
            142,         # Vbat: 14.2V
            128,         # O2
            0x00, 250,   # Inj: 2.50ms
            25,          # Ign: 15 deg
            40,          # ISC
            0x01,        # Flags
        ])

        data = SensorData.from_raw_bytes(raw, timestamp=1700000000.0)
        self.assertEqual(data.engine_speed_rpm, 1500)
        self.assertEqual(data.engine_speed_rps, 25.0)
        self.assertEqual(data.engine_temp_c, 85.0)
        self.assertEqual(data.intake_air_temp_c, 32.0)
        self.assertEqual(data.battery_voltage_v, 14.2)
        self.assertEqual(data.injector_pulse_width_ms, 2.5)
        self.assertTrue(data.gear_neutral)

    def test_ecu_client_full_mock_session(self):
        mock_adapter = MockKLineAdapter(simulate_dtc_codes=[15, 24])
        client = YamahaECUClient(hardware=mock_adapter)

        with client as ecu:
            # 1. Test DTC Reading
            active, history = ecu.diagnostic.read_dtc()
            self.assertEqual(len(active), 2)
            self.assertEqual(active[0].code, 15)
            self.assertEqual(active[1].code, 24)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].code, 46)

            # 2. Test DIAG Item
            diag_tps = ecu.diagnostic.read_diag_item(1) # d01
            self.assertEqual(diag_tps["code"], 1)
            self.assertEqual(diag_tps["raw_value"], 16)
            self.assertTrue(diag_tps["in_range"])

            # 3. Test Live Data Snapshot
            snap = ecu.live_data.read_snapshot()
            self.assertGreater(snap.engine_speed_rpm, 1000)
            self.assertGreater(snap.engine_speed_rps, 15.0)
            self.assertGreater(snap.battery_voltage_v, 12.0)

            # 4. Test CO Trim reading & setting
            co = ecu.mapping.read_co_trim()
            self.assertEqual(co, 2)

            set_ok = ecu.mapping.set_co_trim(5)
            self.assertTrue(set_ok)
            self.assertEqual(ecu.mapping.read_co_trim(), 5)

            # 5. Test Map Profile JSON export/load
            export_file = "scratch_test_mio_gt_map.json"
            try:
                ecu.mapping.export_profile_to_json(export_file)
                self.assertTrue(os.path.exists(export_file))

                loaded_profile = ecu.mapping.load_profile_from_json(export_file)
                self.assertEqual(loaded_profile.model_name, "Yamaha Mio GT 115 YMJET-FI")
                self.assertEqual(loaded_profile.rpm_limiter_rpm, 9500)
                self.assertIsNotNone(loaded_profile.fuel_map)
            finally:
                if os.path.exists(export_file):
                    os.remove(export_file)

            # 6. Test DTC Clearing
            clr_ok = ecu.diagnostic.clear_dtc()
            self.assertTrue(clr_ok)
            active_after, history_after = ecu.diagnostic.read_dtc()
            self.assertEqual(len(active_after), 0)
            self.assertEqual(len(history_after), 0)


if __name__ == "__main__":
    unittest.main()
