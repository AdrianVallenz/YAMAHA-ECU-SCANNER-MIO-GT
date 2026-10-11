"""
Unified Yamaha ECU Client.
Main entry point for interacting with Yamaha Mio GT 2015 ECU (54P / 2BJ Series).
Provides convenient access to Diagnostic, Live Data (RPS), and Mapping services.
"""

from typing import Optional, Union
from ..hardware.interface import KLineInterface
from ..hardware.serial_kline import SerialKLineAdapter
from ..hardware.mock_adapter import MockKLineAdapter
from ..protocol.ydis import YDISProtocol
from ..services.diagnostic import DiagnosticService
from ..services.live_data import LiveDataService
from ..services.mapping import MappingService


class YamahaECUClient:
    """
    High-level Client representing connection to a Yamaha Motorcycle ECU.
    Target vehicle: Yamaha Mio GT 2015 113cc/115cc YMJET-FI.

    Example Usage:
    ```python
    from yamaha_ecu import YamahaECUClient, SerialKLineAdapter

    adapter = SerialKLineAdapter(port="COM3", baudrate=10400)
    with YamahaECUClient(adapter) as ecu:
        # 1. Read Diagnostic Trouble Codes (DTC)
        active, history = ecu.diagnostic.read_dtc()

        # 2. Read Real-time Parameters (RPS / RPM)
        snapshot = ecu.live_data.read_snapshot()
        print(f"RPM: {snapshot.engine_speed_rpm}, RPS: {snapshot.engine_speed_rps}")

        # 3. Read/Modify Mapping & CO trim
        co = ecu.mapping.read_co_trim()
        print(f"Current CO: {co}")
    ```
    """

    def __init__(
        self,
        hardware: Optional[KLineInterface] = None,
        port: str = "COM3",
        baudrate: int = 10400,
        use_mock: bool = False,
    ):
        if hardware is not None:
            self.hardware = hardware
        elif use_mock:
            self.hardware = MockKLineAdapter()
        else:
            self.hardware = SerialKLineAdapter(port=port, baudrate=baudrate)

        self.protocol = YDISProtocol(self.hardware)
        self.diagnostic = DiagnosticService(self.protocol)
        self.live_data = LiveDataService(self.protocol)
        self.mapping = MappingService(self.protocol)

    def connect(self, use_fast_init: bool = True) -> bool:
        """Connects hardware and initializes Yamaha ECU diagnostic session."""
        return self.protocol.initialize_session(use_fast_init=use_fast_init)

    def disconnect(self) -> None:
        """Disconnects session and closes hardware port."""
        if self.live_data.is_streaming():
            self.live_data.stop_stream()
        self.hardware.disconnect()

    def __enter__(self) -> "YamahaECUClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
