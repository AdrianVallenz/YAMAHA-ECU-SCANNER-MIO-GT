"""
Physical Serial K-Line Adapter Implementation.
Compatible with FTDI FT232R, VAG-COM KKL 409.1, CH340, or custom L9637D/MC33660 USB-to-K-Line bridges.
Handles single-wire half-duplex echo cancellation and Yamaha Fast Init wake-up pulses.
"""

import time
from typing import Optional
from .interface import KLineInterface
from ..core.exceptions import HardwareConnectionError

try:
    import serial
except ImportError:
    serial = None


class SerialKLineAdapter(KLineInterface):
    """
    Physical Serial Port K-Line Adapter.
    Yamaha Mio GT 2015 uses K-Line (10400 or 9600 baud, 8-N-1 or 8-E-1).
    """

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 10400,
        parity: str = "N",        # 'N' (None) or 'E' (Even)
        stopbits: int = 1,
        timeout: float = 1.0,
        echo_cancellation: bool = True,
    ):
        self.port = port
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.echo_cancellation = echo_cancellation
        self._serial: Optional["serial.Serial"] = None

    def connect(self) -> bool:
        if serial is None:
            raise HardwareConnectionError(
                "pyserial belum terpasang. Jalankan `pip install pyserial` terlebih dahulu."
            )

        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=parity_map.get(self.parity, serial.PARITY_NONE),
                stopbits=serial.STOPBITS_ONE if self.stopbits == 1 else serial.STOPBITS_TWO,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            # Clear buffers
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            return True
        except Exception as e:
            raise HardwareConnectionError(f"Gagal membuka port serial '{self.port}': {str(e)}")

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def send_break_pulse(self, duration_ms: int = 25) -> None:
        """
        Sends ISO 14230 Fast Init pulse to wake up ECU.
        TiniL: Line LOW for 25ms (+/- 1ms)
        TiniH: Line HIGH for 25ms (+/- 1ms)
        """
        if not self.is_connected():
            raise HardwareConnectionError("Port serial belum terhubung.")

        # Pull K-Line LOW using BREAK or changing baudrate
        self._serial.send_break(duration=duration_ms / 1000.0)
        time.sleep(duration_ms / 1000.0)
        self.flush()

    def write(self, data: bytes) -> int:
        if not self.is_connected():
            raise HardwareConnectionError("Port serial belum terhubung.")

        bytes_written = self._serial.write(data)
        self._serial.flush()

        # On standard single-wire K-Line transceivers (L9637D),
        # what is transmitted on TX echoes back on RX.
        # If echo cancellation is enabled, we consume the echoed bytes.
        if self.echo_cancellation:
            echoed = self._serial.read(len(data))
            # Optional debug check: echoed should match data

        return bytes_written

    def read(self, size: int = 1, timeout_ms: int = 1000) -> bytes:
        if not self.is_connected():
            raise HardwareConnectionError("Port serial belum terhubung.")

        prev_timeout = self._serial.timeout
        self._serial.timeout = timeout_ms / 1000.0
        try:
            data = self._serial.read(size)
            return data
        finally:
            self._serial.timeout = prev_timeout

    def read_until(self, expected_len: int, timeout_ms: int = 1500) -> bytes:
        if not self.is_connected():
            raise HardwareConnectionError("Port serial belum terhubung.")

        start_time = time.time()
        deadline = start_time + (timeout_ms / 1000.0)
        buf = bytearray()

        while len(buf) < expected_len and time.time() < deadline:
            remaining = expected_len - len(buf)
            chunk = self._serial.read(remaining)
            if chunk:
                buf.extend(chunk)
            else:
                time.sleep(0.005)

        return bytes(buf)

    def flush(self) -> None:
        if self.is_connected():
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
