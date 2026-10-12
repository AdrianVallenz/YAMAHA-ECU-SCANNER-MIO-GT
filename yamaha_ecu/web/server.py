"""
HTTP & SSE Server for Yamaha ECU Diagnostic, RPS Telemetry & Tuning Studio.
Provides full ECU access: Live telemetry, interactive 3D/2D table editing,
preset manager, actuator testing, raw packet terminal, and telemetry log management.
100% zero-dependency with standard library http.server.
"""

import os
import sys
import time
import json
import csv
import queue
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional, List

from ..core.ecu_client import YamahaECUClient
from ..hardware.serial_kline import SerialKLineAdapter
from ..hardware.mock_adapter import MockKLineAdapter
from ..models.sensor_data import SensorData
from ..models.map_tables import ECUMappingProfile, MapTable3D
from ..plotter import plot_telemetry_csv


class ECUBridge:
    """Thread-safe manager bridging ECU hardware/mock to web clients."""

    def __init__(self, default_mock: bool = True, default_port: str = "COM3", default_baud: int = 10400):
        self.lock = threading.Lock()
        self.default_mock = default_mock
        self.port = default_port
        self.baudrate = default_baud

        self.client: Optional[YamahaECUClient] = None
        self.is_mock: bool = default_mock
        self.is_connected: bool = False

        self.active_profile: ECUMappingProfile = ECUMappingProfile.create_default_mio_gt()

        self.latest_data: Optional[Dict[str, Any]] = None
        self.sse_queues: List[queue.Queue] = []
        self._worker_running = False
        self._worker_thread: Optional[threading.Thread] = None

        # CSV Recording
        self.recording_file = None
        self.csv_writer = None
        self.recording_path: Optional[str] = None
        self.recorded_samples: int = 0

        # Auto-connect initially
        self.connect(mock=default_mock, port=default_port, baudrate=default_baud)

    def get_serial_ports(self) -> List[str]:
        """Scan available serial ports."""
        try:
            import serial.tools.list_ports
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return ["COM1", "COM2", "COM3", "COM4", "COM5"]

    def connect(self, mock: bool = True, port: str = "COM3", baudrate: int = 10400) -> Dict[str, Any]:
        with self.lock:
            self._disconnect_internal()

            self.is_mock = mock
            self.port = port
            self.baudrate = baudrate

            try:
                if mock:
                    adapter = MockKLineAdapter()
                else:
                    adapter = SerialKLineAdapter(port=port, baudrate=baudrate)

                self.client = YamahaECUClient(hardware=adapter)
                self.client.connect()
                self.is_connected = True

                self._worker_running = True
                self._worker_thread = threading.Thread(target=self._telemetry_worker, daemon=True)
                self._worker_thread.start()

                return {"status": "ok", "connected": True, "mode": "mock" if mock else "serial", "port": port}
            except Exception as e:
                self.is_connected = False
                self.client = None
                return {"status": "error", "message": str(e)}

    def disconnect(self) -> Dict[str, Any]:
        with self.lock:
            self._disconnect_internal()
            return {"status": "ok", "connected": False}

    def _disconnect_internal(self) -> None:
        self._worker_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

        self.stop_recording()

        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None
        self.is_connected = False

    def _telemetry_worker(self) -> None:
        """Poll telemetry at 15-20 Hz and broadcast to all SSE subscribers."""
        while self._worker_running and self.client and self.is_connected:
            t0 = time.time()
            try:
                data: SensorData = self.client.live_data.read_snapshot()
                d_dict = data.to_dict()
                self.latest_data = d_dict

                # Save to CSV if recording
                if self.csv_writer:
                    self.csv_writer.writerow(d_dict)
                    self.recording_file.flush()
                    self.recorded_samples += 1

                # Broadcast to SSE queues
                msg = f"data: {json.dumps(d_dict)}\n\n"
                dead_queues = []
                for q in self.sse_queues:
                    try:
                        q.put_nowait(msg)
                    except queue.Full:
                        pass
                    except Exception:
                        dead_queues.append(q)

                for dq in dead_queues:
                    if dq in self.sse_queues:
                        self.sse_queues.remove(dq)

            except Exception:
                time.sleep(0.05)

            elapsed = time.time() - t0
            sleep_time = max(0.01, 0.05 - elapsed)
            time.sleep(sleep_time)

    def register_sse(self) -> queue.Queue:
        q = queue.Queue(maxsize=20)
        self.sse_queues.append(q)
        return q

    def unregister_sse(self, q: queue.Queue) -> None:
        if q in self.sse_queues:
            self.sse_queues.remove(q)

    def read_dtc(self) -> Dict[str, Any]:
        with self.lock:
            if not self.client or not self.is_connected:
                return {"active": [], "history": [], "error": "Not connected"}
            try:
                active, history = self.client.diagnostic.read_dtc()
                return {
                    "active": [
                        {
                            "code": f.code,
                            "name": f.name,
                            "description": f.description,
                            "symptoms": f.symptoms,
                            "probable_cause": f.probable_cause,
                            "is_active": True,
                        }
                        for f in active
                    ],
                    "history": [
                        {
                            "code": f.code,
                            "name": f.name,
                            "description": f.description,
                            "symptoms": f.symptoms,
                            "probable_cause": f.probable_cause,
                            "is_active": False,
                        }
                        for f in history
                    ],
                }
            except Exception as e:
                return {"active": [], "history": [], "error": str(e)}

    def clear_dtc(self) -> Dict[str, Any]:
        with self.lock:
            if not self.client or not self.is_connected:
                return {"success": False, "error": "Not connected"}
            try:
                ok = self.client.diagnostic.clear_dtc()
                return {"success": ok}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def read_diag(self) -> List[Dict[str, Any]]:
        with self.lock:
            if not self.client or not self.is_connected:
                return []
            try:
                return self.client.diagnostic.run_all_sensor_diagnostics()
            except Exception:
                return []

    # =====================================================================
    # ECU MAPPING & CALIBRATION TUNING
    # =====================================================================
    def get_mapping_profile(self) -> Dict[str, Any]:
        with self.lock:
            current_co = 0
            if self.client and self.is_connected:
                try:
                    current_co = self.client.mapping.read_co_trim()
                except Exception:
                    pass
            self.active_profile.co_adjustment_trim = current_co
            return json.loads(self.active_profile.to_json())

    def update_map_cell(self, map_type: str, row: int, col: int, value: float) -> Dict[str, Any]:
        with self.lock:
            table = self.active_profile.fuel_map if map_type == "fuel" else self.active_profile.ignition_map
            if table and 0 <= row < len(table.matrix) and 0 <= col < len(table.matrix[row]):
                table.set_cell(row, col, round(float(value), 2))
                return {"success": True, "map_type": map_type, "row": row, "col": col, "value": round(float(value), 2)}
            return {"success": False, "error": "Invalid row/column coordinates"}

    def apply_fuel_trim(self, percentage: float) -> Dict[str, Any]:
        with self.lock:
            if not self.active_profile.fuel_map:
                return {"success": False, "error": "Fuel map not initialized"}
            factor = 1.0 + (percentage / 100.0)
            for r in range(len(self.active_profile.fuel_map.matrix)):
                for c in range(len(self.active_profile.fuel_map.matrix[r])):
                    curr = self.active_profile.fuel_map.matrix[r][c]
                    self.active_profile.fuel_map.matrix[r][c] = round(curr * factor, 2)
            return {"success": True, "applied_percentage": percentage}

    def apply_ignition_trim(self, deg_offset: float) -> Dict[str, Any]:
        with self.lock:
            if not self.active_profile.ignition_map:
                return {"success": False, "error": "Ignition map not initialized"}
            for r in range(len(self.active_profile.ignition_map.matrix)):
                for c in range(len(self.active_profile.ignition_map.matrix[r])):
                    curr = self.active_profile.ignition_map.matrix[r][c]
                    self.active_profile.ignition_map.matrix[r][c] = round(max(0.0, curr + deg_offset), 1)
            return {"success": True, "applied_deg": deg_offset}

    def set_co_trim(self, co_value: int) -> Dict[str, Any]:
        with self.lock:
            if not self.client or not self.is_connected:
                return {"success": False, "error": "Not connected"}
            try:
                ok = self.client.mapping.set_co_trim(co_value)
                return {"success": ok, "co_trim": co_value}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def list_presets(self) -> List[Dict[str, Any]]:
        presets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "presets")
        results = []
        if os.path.exists(presets_dir):
            for fname in os.listdir(presets_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(presets_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            d = json.load(f)
                            results.append({
                                "filename": fname,
                                "name": d.get("model_name", fname),
                                "co": d.get("co_adjustment_trim", 0),
                                "limiter": d.get("rpm_limiter_rpm", 9500),
                            })
                    except Exception:
                        results.append({"filename": fname, "name": fname, "co": 0, "limiter": 9500})
        return results

    def load_preset(self, filename: str) -> Dict[str, Any]:
        presets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "presets")
        fpath = os.path.join(presets_dir, os.path.basename(filename))
        if not os.path.exists(fpath):
            return {"success": False, "error": f"Preset {filename} not found"}
        with self.lock:
            try:
                if self.client:
                    self.active_profile = self.client.mapping.load_profile_from_json(fpath)
                else:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.active_profile = ECUMappingProfile(
                        model_name=data.get("model_name", "Yamaha Mio GT 115"),
                        ecu_part_number=data.get("ecu_part_number", "54P-H591A-00"),
                        firmware_version=data.get("firmware_version", "v1.00"),
                        rpm_limiter_rpm=data.get("rpm_limiter_rpm", 9500),
                        soft_limiter_rpm=data.get("soft_limiter_rpm", 9300),
                        idle_target_cold_rpm=data.get("idle_target_cold_rpm", 1800),
                        idle_target_warm_rpm=data.get("idle_target_warm_rpm", 1400),
                        co_adjustment_trim=data.get("co_adjustment_trim", 0),
                    )
                    if "fuel_map" in data and data["fuel_map"]:
                        fm = data["fuel_map"]
                        self.active_profile.fuel_map = MapTable3D(
                            name=fm["name"], description=fm["description"],
                            rpm_axis=fm["rpm_axis"], load_axis=fm["load_axis"],
                            load_axis_name=fm["load_axis_name"], matrix=fm["matrix"], unit=fm["unit"],
                        )
                    if "ignition_map" in data and data["ignition_map"]:
                        im = data["ignition_map"]
                        self.active_profile.ignition_map = MapTable3D(
                            name=im["name"], description=im["description"],
                            rpm_axis=im["rpm_axis"], load_axis=im["load_axis"],
                            load_axis_name=im["load_axis_name"], matrix=im["matrix"], unit=im["unit"],
                        )
                return {"success": True, "profile": json.loads(self.active_profile.to_json())}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def trigger_actuator(self, test_code: int) -> Dict[str, Any]:
        with self.lock:
            if not self.client or not self.is_connected:
                return {"success": False, "error": "Not connected to ECU"}
            try:
                ok = self.client.diagnostic.trigger_actuator_test(test_code)
                return {"success": ok, "test_code": test_code}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def send_raw_command(self, hex_string: str) -> Dict[str, Any]:
        with self.lock:
            if not self.client or not self.is_connected:
                return {"success": False, "error": "Not connected to ECU"}
            try:
                cleaned = hex_string.replace("0x", "").replace(" ", "").replace(",", "").strip()
                raw_bytes = bytes.fromhex(cleaned)
                if len(raw_bytes) == 1:
                    cmd = raw_bytes[0]
                    resp_id, payload = self.client.protocol.send_command(cmd)
                    full_resp = bytes([resp_id]) + payload
                    return {
                        "success": True,
                        "request_hex": raw_bytes.hex().upper(),
                        "response_hex": full_resp.hex().upper(),
                        "resp_cmd": f"0x{resp_id:02X}",
                        "payload_len": len(payload),
                    }
                else:
                    self.client.hardware.flush()
                    self.client.hardware.write(raw_bytes)
                    time.sleep(0.08)
                    resp = self.client.hardware.read(64, timeout_ms=600)
                    return {
                        "success": True,
                        "request_hex": raw_bytes.hex().upper(),
                        "response_hex": resp.hex().upper() if resp else "NO_RESPONSE",
                        "len": len(resp) if resp else 0,
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

    # =====================================================================
    # TELEMETRY LOG RECORDINGS & SESSIONS
    # =====================================================================
    def start_recording(self) -> Dict[str, Any]:
        if self.csv_writer:
            return {"status": "already_recording", "path": self.recording_path}

        filename = f"telemetry_log_{int(time.time())}.csv"
        path = os.path.abspath(filename)
        try:
            self.recording_file = open(path, mode="w", newline="", encoding="utf-8")
            fields = list(self.latest_data.keys()) if self.latest_data else [
                "timestamp", "engine_speed_rpm", "engine_speed_rps", "throttle_position_pct",
                "throttle_angle_deg", "throttle_voltage_v", "engine_temp_c", "intake_air_temp_c",
                "manifold_pressure_kpa", "atmospheric_pressure_kpa", "battery_voltage_v",
                "o2_sensor_voltage_v", "o2_lambda", "injector_pulse_width_ms", "ignition_advance_deg",
                "isc_valve_steps", "gear_neutral", "kickstand_down", "tip_over_sensor_v",
                "fuel_consumption_l_per_h", "formatted_time"
            ]
            self.csv_writer = csv.DictWriter(self.recording_file, fieldnames=fields)
            self.csv_writer.writeheader()
            self.recording_path = path
            self.recorded_samples = 0
            return {"status": "recording_started", "path": path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop_recording(self) -> Dict[str, Any]:
        if not self.csv_writer:
            return {"status": "not_recording"}

        path = self.recording_path
        samples = self.recorded_samples
        try:
            if self.recording_file:
                self.recording_file.close()
        except Exception:
            pass
        self.recording_file = None
        self.csv_writer = None
        self.recording_path = None
        self.recorded_samples = 0
        return {"status": "recording_stopped", "path": path, "samples": samples}

    def list_recordings(self) -> List[Dict[str, Any]]:
        results = []
        cwd = os.getcwd()
        for f in os.listdir(cwd):
            if f.startswith("telemetry_log_") and f.endswith(".csv"):
                fpath = os.path.join(cwd, f)
                try:
                    stat = os.stat(fpath)
                    line_count = 0
                    with open(fpath, "r", encoding="utf-8") as fl:
                        for _ in fl:
                            line_count += 1
                    results.append({
                        "filename": f,
                        "size_kb": round(stat.st_size / 1024, 1),
                        "timestamp": stat.st_mtime,
                        "formatted_date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                        "samples": max(0, line_count - 1),
                    })
                except Exception:
                    pass
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results


class DashboardHandler(BaseHTTPRequestHandler):
    """Handles static files, REST API, file downloads, and Server-Sent Events (SSE)."""

    bridge: ECUBridge = None  # Injected class variable
    static_dir: str = os.path.join(os.path.dirname(__file__), "static")

    def log_message(self, format, *args):
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/status":
            self._send_json({
                "connected": self.bridge.is_connected,
                "mode": "mock" if self.bridge.is_mock else "serial",
                "port": self.bridge.port,
                "baudrate": self.bridge.baudrate,
                "model": "Yamaha Mio GT 115 YMJET-FI (2013-2015)",
                "ecu_part": "54P-H591A-00",
                "is_recording": bool(self.bridge.csv_writer),
                "recorded_samples": self.bridge.recorded_samples,
            })
            return

        elif path == "/api/ports":
            ports = self.bridge.get_serial_ports()
            self._send_json(ports)
            return

        elif path == "/api/telemetry":
            data = self.bridge.latest_data or {}
            self._send_json(data)
            return

        elif path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q = self.bridge.register_sse()
            try:
                if self.bridge.latest_data:
                    self.wfile.write(f"data: {json.dumps(self.bridge.latest_data)}\n\n".encode("utf-8"))
                    self.wfile.flush()

                while True:
                    try:
                        msg = q.get(timeout=1.0)
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.bridge.unregister_sse(q)
            return

        elif path == "/api/dtc":
            res = self.bridge.read_dtc()
            self._send_json(res)
            return

        elif path == "/api/diag":
            res = self.bridge.read_diag()
            self._send_json(res)
            return

        elif path == "/api/mapping":
            res = self.bridge.get_mapping_profile()
            self._send_json(res)
            return

        elif path == "/api/mapping/presets":
            res = self.bridge.list_presets()
            self._send_json(res)
            return

        elif path == "/api/recordings":
            res = self.bridge.list_recordings()
            self._send_json(res)
            return

        elif path == "/api/recordings/download":
            fname = query.get("file", [""])[0]
            clean_name = os.path.basename(fname)
            fpath = os.path.abspath(clean_name)
            if os.path.exists(fpath) and clean_name.endswith(".csv"):
                with open(fpath, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{clean_name}"')
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self.send_error(404, "Recording file not found")
            return

        # Static files
        if path in ("/", "/index.html"):
            self._serve_file(os.path.join(self.static_dir, "index.html"), "text/html; charset=utf-8")
        elif path == "/style.css":
            self._serve_file(os.path.join(self.static_dir, "style.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_file(os.path.join(self.static_dir, "app.js"), "application/javascript; charset=utf-8")
        else:
            target = os.path.join(self.static_dir, path.lstrip("/"))
            if os.path.isfile(target):
                content_type = "text/plain"
                if target.endswith(".html"):
                    content_type = "text/html; charset=utf-8"
                elif target.endswith(".css"):
                    content_type = "text/css; charset=utf-8"
                elif target.endswith(".js"):
                    content_type = "application/javascript; charset=utf-8"
                elif target.endswith(".svg"):
                    content_type = "image/svg+xml"
                elif target.endswith(".png"):
                    content_type = "image/png"
                self._serve_file(target, content_type)
            else:
                # Check root directory for generated png files
                root_target = os.path.abspath(path.lstrip("/"))
                if os.path.isfile(root_target) and root_target.endswith(".png"):
                    self._serve_file(root_target, "image/png")
                else:
                    self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception:
            payload = {}

        if path == "/api/connect":
            mock = payload.get("mock", True)
            port = payload.get("port", "COM3")
            baud = int(payload.get("baudrate", 10400))
            res = self.bridge.connect(mock=mock, port=port, baudrate=baud)
            self._send_json(res)
            return

        elif path == "/api/disconnect":
            res = self.bridge.disconnect()
            self._send_json(res)
            return

        elif path == "/api/dtc/clear":
            res = self.bridge.clear_dtc()
            self._send_json(res)
            return

        elif path == "/api/mapping/co":
            val = int(payload.get("co_trim", 0))
            res = self.bridge.set_co_trim(val)
            self._send_json(res)
            return

        elif path == "/api/mapping/cell":
            m_type = payload.get("map_type", "fuel")
            row = int(payload.get("row", 0))
            col = int(payload.get("col", 0))
            val = float(payload.get("value", 0.0))
            res = self.bridge.update_map_cell(m_type, row, col, val)
            self._send_json(res)
            return

        elif path == "/api/mapping/trim":
            m_type = payload.get("type", "fuel")
            delta = float(payload.get("delta", 0.0))
            if m_type == "fuel":
                res = self.bridge.apply_fuel_trim(delta)
            else:
                res = self.bridge.apply_ignition_trim(delta)
            self._send_json(res)
            return

        elif path == "/api/mapping/load_preset":
            fname = payload.get("filename", "")
            res = self.bridge.load_preset(fname)
            self._send_json(res)
            return

        elif path == "/api/actuator/test":
            code = int(payload.get("test_code", 30))
            res = self.bridge.trigger_actuator(code)
            self._send_json(res)
            return

        elif path == "/api/raw":
            cmd = payload.get("hex_command", "")
            res = self.bridge.send_raw_command(cmd)
            self._send_json(res)
            return

        elif path == "/api/recording/start":
            res = self.bridge.start_recording()
            self._send_json(res)
            return

        elif path == "/api/recording/stop":
            res = self.bridge.stop_recording()
            self._send_json(res)
            return

        elif path == "/api/recordings/plot":
            fname = payload.get("filename", "")
            clean = os.path.basename(fname)
            if os.path.exists(clean):
                try:
                    img_path = plot_telemetry_csv(clean)
                    self._send_json({"success": True, "image": os.path.basename(img_path)})
                    return
                except Exception as e:
                    self._send_json({"success": False, "error": str(e)})
                    return
            self._send_json({"success": False, "error": "File not found"})
            return

        self.send_error(404, "Unknown API Endpoint")

    def _serve_file(self, file_path: str, content_type: str) -> None:
        if not os.path.exists(file_path):
            self.send_error(404, f"File not found: {os.path.basename(file_path)}")
            return

        with open(file_path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def start_web_server(
    port: int = 8000,
    mock: bool = True,
    serial_port: str = "COM3",
    baudrate: int = 10400,
    open_browser: bool = True,
) -> None:
    """Starts the Threading HTTP Server and optionally opens the browser."""
    bridge = ECUBridge(default_mock=mock, default_port=serial_port, default_baud=baudrate)
    DashboardHandler.bridge = bridge

    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, DashboardHandler)

    url = f"http://localhost:{port}"
    print("=" * 72)
    print(" 🚀 YAMAHA ECU STUDIO & TUNING SUITE")
    print(f"    Mode          : {'[SIMULATOR MOCK]' if mock else f'[SERIAL K-LINE: {serial_port} @ {baudrate}]'}")
    print(f"    Web Dashboard : {url}")
    print(f"    Target        : Yamaha Mio GT 115cc YMJET-FI (ECU 54P-H591A-00)")
    print("=" * 72)
    print(" Server berjalan. Tekan Ctrl+C di terminal untuk menghentikan.")

    if open_browser:
        def _opener():
            time.sleep(0.8)
            import webbrowser
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_opener, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Menghentikan server visual...")
    finally:
        bridge.disconnect()
        httpd.server_close()
        print("[v] Server visual dashboard berhasil dimatikan.")
