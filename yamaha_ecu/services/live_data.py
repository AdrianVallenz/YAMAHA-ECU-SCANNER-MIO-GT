"""
Real-time Parameter Streaming (RPS / Live Data) Service for Yamaha Mio GT 2015.
Streams live sensor parameters: Engine RPM, RPS, Throttle (TPS), MAP, Temperature, Battery, O2.
Includes CSV logging and async/threaded streaming callbacks.
"""

import time
import csv
import threading
from typing import Callable, Optional
from ..protocol.ydis import YDISProtocol
from ..protocol.constants import YDIS_CMD_READ_LIVE_DATA
from ..models.sensor_data import SensorData


class LiveDataService:
    """Service to handle real-time engine telemetry streaming from Yamaha ECU."""

    def __init__(self, protocol: YDISProtocol):
        self.protocol = protocol
        self._streaming = False
        self._thread: Optional[threading.Thread] = None

    def read_snapshot(self) -> SensorData:
        """
        Fetches a single instantaneous telemetry frame from the ECU.
        """
        resp_id, payload = self.protocol.send_command(YDIS_CMD_READ_LIVE_DATA)
        # Payload starts with response identifier 0x61
        raw_data = payload[1:] if (len(payload) > 0 and payload[0] == 0x61) else payload
        return SensorData.from_raw_bytes(raw_data)

    def start_stream(
        self,
        callback: Callable[[SensorData], None],
        interval_ms: int = 100,
        csv_log_path: Optional[str] = None,
    ) -> None:
        """
        Starts non-blocking background streaming thread.
        Calls `callback(sensor_data)` on each received frame.
        Optionally writes telemetry to a CSV file.
        """
        if self._streaming:
            return

        self._streaming = True
        self._thread = threading.Thread(
            target=self._stream_worker,
            args=(callback, interval_ms, csv_log_path),
            daemon=True,
        )
        self._thread.start()

    def stop_stream(self) -> None:
        """Stops the active telemetry streaming thread."""
        self._streaming = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def is_streaming(self) -> bool:
        return self._streaming

    def _stream_worker(
        self,
        callback: Callable[[SensorData], None],
        interval_ms: int,
        csv_log_path: Optional[str],
    ) -> None:
        csv_file = None
        csv_writer = None

        if csv_log_path:
            csv_file = open(csv_log_path, mode="w", newline="", encoding="utf-8")
            # Write header from dataclass fields
            snapshot = self.read_snapshot()
            csv_writer = csv.DictWriter(csv_file, fieldnames=list(snapshot.to_dict().keys()))
            csv_writer.writeheader()
            csv_writer.writerow(snapshot.to_dict())
            callback(snapshot)

        delay_sec = interval_ms / 1000.0

        while self._streaming:
            t_start = time.time()
            try:
                data = self.read_snapshot()
                if csv_writer:
                    csv_writer.writerow(data.to_dict())
                    csv_file.flush()
                callback(data)
            except Exception as e:
                # Log or handle intermittent read errors
                pass

            t_elapsed = time.time() - t_start
            t_sleep = max(0.005, delay_sec - t_elapsed)
            time.sleep(t_sleep)

        if csv_file:
            csv_file.close()
