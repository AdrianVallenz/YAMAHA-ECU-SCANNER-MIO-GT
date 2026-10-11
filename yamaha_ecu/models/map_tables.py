"""
ECU Mapping and Calibration Table Models.
Represents Fuel injection maps, Ignition timing maps, RPM limiters, and CO trim parameters.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class MapTable2D:
    """Represents a 1D/2D curve (e.g. Temperature vs Enrichment or RPM vs Target)."""
    name: str
    description: str
    x_axis_name: str
    x_axis_values: List[float]
    values: List[float]
    unit: str

    def interpolate(self, x: float) -> float:
        """Linear interpolation for lookup."""
        if not self.x_axis_values or not self.values:
            return 0.0
        if x <= self.x_axis_values[0]:
            return self.values[0]
        if x >= self.x_axis_values[-1]:
            return self.values[-1]
        for i in range(len(self.x_axis_values) - 1):
            if self.x_axis_values[i] <= x <= self.x_axis_values[i + 1]:
                x0, x1 = self.x_axis_values[i], self.x_axis_values[i + 1]
                y0, y1 = self.values[i], self.values[i + 1]
                t = (x - x0) / (x1 - x0) if x1 != x0 else 0
                return y0 + t * (y1 - y0)
        return self.values[-1]


@dataclass
class MapTable3D:
    """
    Represents a 3D matrix map (e.g. RPM [columns] x TPS% [rows] -> Value).
    Used for Fuel Injection (ms or VE%) and Ignition Timing (deg BTDC).
    """
    name: str
    description: str
    rpm_axis: List[int]             # Columns: RPM (e.g. [1000, 1500, 2000, ..., 9500])
    load_axis: List[float]          # Rows: TPS (%) or MAP (kPa)
    load_axis_name: str             # "TPS (%)" or "MAP (kPa)"
    matrix: List[List[float]]       # 2D grid [row_idx][col_idx]
    unit: str                       # "deg BTDC" or "ms" or "% VE"

    def get_cell(self, load_idx: int, rpm_idx: int) -> float:
        return self.matrix[load_idx][rpm_idx]

    def set_cell(self, load_idx: int, rpm_idx: int, value: float) -> None:
        self.matrix[load_idx][rpm_idx] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "rpm_axis": self.rpm_axis,
            "load_axis": self.load_axis,
            "load_axis_name": self.load_axis_name,
            "matrix": self.matrix,
            "unit": self.unit,
        }


@dataclass
class ECUMappingProfile:
    """Complete ECU Mapping profile containing Fuel, Ignition, and Calibration limits."""
    model_name: str = "Yamaha Mio GT 115 YMJET-FI"
    ecu_part_number: str = "54P-H591A-00"
    firmware_version: str = "v1.02_MIO_GT"
    rpm_limiter_rpm: int = 9500
    soft_limiter_rpm: int = 9300
    idle_target_cold_rpm: int = 1800
    idle_target_warm_rpm: int = 1400
    co_adjustment_trim: int = 0        # -30 to +30 range in Yamaha Y-DIS
    fuel_map: Optional[MapTable3D] = None
    ignition_map: Optional[MapTable3D] = None

    @classmethod
    def create_default_mio_gt(cls) -> "ECUMappingProfile":
        """Factory for stock Yamaha Mio GT 2015 113cc (54P) map calibration."""
        # Standard RPM axis for 115cc single cylinder scooter
        rpm_axis = [1200, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 9500]
        # TPS load axis (%)
        tps_axis = [0.0, 5.0, 10.0, 20.0, 35.0, 50.0, 70.0, 100.0]

        # Fuel Injection Matrix (in milliseconds pulse width or VE baseline)
        fuel_matrix = [
            # 0% TPS (Deceleration / Idle)
            [1.8, 1.6, 1.4, 1.2, 1.1, 1.0, 1.0, 1.0, 1.0, 1.0],
            # 5% TPS (Light cruise)
            [2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.6, 2.7, 2.7, 2.6],
            # 10% TPS
            [2.3, 2.5, 2.7, 2.9, 3.1, 3.2, 3.3, 3.4, 3.4, 3.2],
            # 20% TPS (Normal city acceleration)
            [2.6, 2.9, 3.3, 3.7, 4.1, 4.4, 4.6, 4.7, 4.6, 4.3],
            # 35% TPS
            [3.0, 3.5, 4.1, 4.8, 5.3, 5.8, 6.1, 6.2, 6.0, 5.5],
            # 50% TPS (Overtaking)
            [3.4, 4.0, 4.9, 5.8, 6.6, 7.2, 7.5, 7.6, 7.4, 6.8],
            # 70% TPS
            [3.8, 4.5, 5.6, 6.7, 7.6, 8.3, 8.7, 8.8, 8.5, 7.8],
            # 100% TPS (Wide Open Throttle - WOT)
            [4.0, 4.9, 6.1, 7.4, 8.4, 9.2, 9.6, 9.7, 9.4, 8.5],
        ]

        # Ignition Timing Matrix (Degrees BTDC)
        # Low load/idle ~ 5°-10°, mid load ~ 25°-32°, high load/high RPM ~ 28°-35°
        ign_matrix = [
            # 0% TPS
            [7.0, 12.0, 20.0, 28.0, 32.0, 35.0, 36.0, 36.0, 35.0, 34.0],
            # 5% TPS
            [8.0, 14.0, 22.0, 29.0, 33.0, 35.0, 36.0, 36.0, 35.0, 34.0],
            # 10% TPS
            [9.0, 15.0, 23.0, 29.0, 33.0, 35.0, 35.0, 35.0, 34.0, 33.0],
            # 20% TPS
            [9.0, 16.0, 23.0, 28.0, 32.0, 34.0, 34.0, 34.0, 33.0, 32.0],
            # 35% TPS
            [10.0, 16.0, 22.0, 27.0, 30.0, 32.0, 33.0, 33.0, 32.0, 31.0],
            # 50% TPS
            [10.0, 16.0, 21.0, 26.0, 29.0, 31.0, 32.0, 32.0, 31.0, 30.0],
            # 70% TPS
            [10.0, 15.0, 20.0, 25.0, 28.0, 30.0, 31.0, 31.0, 30.0, 29.0],
            # 100% TPS
            [10.0, 15.0, 19.0, 24.0, 27.0, 29.0, 30.0, 30.0, 29.0, 28.0],
        ]

        fuel_map = MapTable3D(
            name="Main Fuel Injection Map",
            description="Tabel durasi injeksi bahan bakar dasar (Base Fuel Pulse Width) Mio GT 115cc",
            rpm_axis=rpm_axis,
            load_axis=tps_axis,
            load_axis_name="TPS (%)",
            matrix=fuel_matrix,
            unit="ms",
        )

        ignition_map = MapTable3D(
            name="Base Ignition Timing Map",
            description="Tabel derajat pengapian (Ignition Advance BTDC) Mio GT 115cc",
            rpm_axis=rpm_axis,
            load_axis=tps_axis,
            load_axis_name="TPS (%)",
            matrix=ign_matrix,
            unit="deg BTDC",
        )

        return cls(
            model_name="Yamaha Mio GT 115 YMJET-FI",
            ecu_part_number="54P-H591A-00",
            firmware_version="v1.02_MIO_GT",
            rpm_limiter_rpm=9500,
            soft_limiter_rpm=9300,
            idle_target_cold_rpm=1800,
            idle_target_warm_rpm=1400,
            co_adjustment_trim=0,
            fuel_map=fuel_map,
            ignition_map=ignition_map,
        )

    def to_json(self) -> str:
        data = {
            "model_name": self.model_name,
            "ecu_part_number": self.ecu_part_number,
            "firmware_version": self.firmware_version,
            "rpm_limiter_rpm": self.rpm_limiter_rpm,
            "soft_limiter_rpm": self.soft_limiter_rpm,
            "idle_target_cold_rpm": self.idle_target_cold_rpm,
            "idle_target_warm_rpm": self.idle_target_warm_rpm,
            "co_adjustment_trim": self.co_adjustment_trim,
            "fuel_map": self.fuel_map.to_dict() if self.fuel_map else None,
            "ignition_map": self.ignition_map.to_dict() if self.ignition_map else None,
        }
        return json.dumps(data, indent=2)
