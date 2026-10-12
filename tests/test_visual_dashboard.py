"""
Unit and Integration Tests for Yamaha ECU Visual Dashboard & Web Telemetry Server.
Zero-dependency testing with Python standard library unittest.
"""

import os
import time
import json
import unittest
import threading
from urllib.request import urlopen, Request
from http.server import ThreadingHTTPServer

from yamaha_ecu.web.server import ECUBridge, DashboardHandler
from yamaha_ecu.plotter import plot_telemetry_csv, plot_ecu_maps


class TestVisualDashboard(unittest.TestCase):

    def setUp(self):
        self.bridge = ECUBridge(default_mock=True, default_port="COM3", default_baud=10400)
        time.sleep(0.1)

    def tearDown(self):
        self.bridge.disconnect()

    def test_bridge_mock_telemetry(self):
        self.assertTrue(self.bridge.is_connected)
        self.assertTrue(self.bridge.is_mock)

        # Allow worker to collect at least one frame
        time.sleep(0.15)
        data = self.bridge.latest_data
        self.assertIsNotNone(data)
        self.assertIn("engine_speed_rpm", data)
        self.assertIn("engine_speed_rps", data)
        self.assertGreater(data["engine_speed_rpm"], 1000)

    def test_bridge_dtc_and_clear(self):
        dtc_data = self.bridge.read_dtc()
        self.assertIn("active", dtc_data)
        self.assertIn("history", dtc_data)
        self.assertGreaterEqual(len(dtc_data["active"]), 1)

        # Clear DTC
        res = self.bridge.clear_dtc()
        self.assertTrue(res.get("success"))

        dtc_after = self.bridge.read_dtc()
        self.assertEqual(len(dtc_after["active"]), 0)

    def test_bridge_diag_inspection(self):
        diag_items = self.bridge.read_diag()
        self.assertIsInstance(diag_items, list)
        self.assertGreater(len(diag_items), 0)
        self.assertTrue(any(item["code"] == 1 for item in diag_items))

    def test_bridge_co_trim(self):
        profile = self.bridge.get_mapping_profile()
        self.assertIn("fuel_map", profile)
        self.assertIn("ignition_map", profile)

        res = self.bridge.set_co_trim(8)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("co_trim"), 8)

    def test_bridge_csv_recording(self):
        # Wait for data
        time.sleep(0.15)
        res_start = self.bridge.start_recording()
        self.assertEqual(res_start["status"], "recording_started")
        rec_path = res_start["path"]

        # Collect a few samples
        time.sleep(0.2)
        res_stop = self.bridge.stop_recording()
        self.assertEqual(res_stop["status"], "recording_stopped")
        self.assertGreater(res_stop["samples"], 0)
        self.assertTrue(os.path.exists(rec_path))

        # Test Plotter on this recorded CSV
        try:
            plot_path = plot_telemetry_csv(rec_path)
            self.assertTrue(os.path.exists(plot_path))
            if os.path.exists(plot_path):
                os.remove(plot_path)
        finally:
            if os.path.exists(rec_path):
                os.remove(rec_path)

    def test_plot_ecu_maps(self):
        out_img = "test_scratch_maps.png"
        try:
            res = plot_ecu_maps(save_image_path=out_img)
            self.assertTrue(os.path.exists(out_img))
        finally:
            if os.path.exists(out_img):
                os.remove(out_img)


class TestWebServerHTTP(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bridge = ECUBridge(default_mock=True)
        DashboardHandler.bridge = cls.bridge
        cls.port = 18080
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), DashboardHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.bridge.disconnect()
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = Request(url)
        with urlopen(req) as resp:
            return resp.status, resp.headers.get_content_type(), resp.read()

    def test_static_index_html(self):
        status, ctype, content = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"YAMAHA ECU STUDIO", content)

    def test_static_style_css(self):
        status, ctype, content = self._get("/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", ctype)
        self.assertIn(b"yamaha-blue", content)

    def test_static_app_js(self):
        status, ctype, content = self._get("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)
        self.assertIn(b"RadialGauge", content)

    def test_api_status(self):
        status, ctype, content = self._get("/api/status")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertTrue(data.get("connected"))
        self.assertEqual(data.get("mode"), "mock")

    def test_api_telemetry(self):
        time.sleep(0.15)
        status, ctype, content = self._get("/api/telemetry")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertIn("engine_speed_rpm", data)

    def test_api_mapping(self):
        status, ctype, content = self._get("/api/mapping")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertIn("fuel_map", data)
        self.assertIn("ignition_map", data)

    def _post(self, path: str, payload: dict):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urlopen(req) as resp:
            return resp.status, resp.headers.get_content_type(), resp.read()

    def test_api_mapping_cell_update(self):
        status, _, content = self._post("/api/mapping/cell", {"map_type": "fuel", "row": 0, "col": 0, "value": 2.5})
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("value"), 2.5)

    def test_api_presets(self):
        status, _, content = self._get("/api/mapping/presets")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_api_actuator_test(self):
        status, _, content = self._post("/api/actuator/test", {"test_code": 30})
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertTrue(data.get("success"))

    def test_api_raw_terminal(self):
        status, _, content = self._post("/api/raw", {"hex_command": "21"})
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertIn("response_hex", data)

    def test_api_recordings_list(self):
        status, _, content = self._get("/api/recordings")
        self.assertEqual(status, 200)
        data = json.loads(content.decode("utf-8"))
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
