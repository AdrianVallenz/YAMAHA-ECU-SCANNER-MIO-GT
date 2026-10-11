"""
ECU Mapping and Calibration Service for Yamaha Mio GT 2015.
Provides tools to:
- Read & Write CO Adjustment Trims (-30 to +30) via Y-DIS protocol.
- Read RPM limits and engine threshold configurations.
- Parse, visualize, modify, and export 2D/3D Fuel & Ignition maps (JSON, CSV, BIN).
"""

import json
import csv
from typing import Dict, Any, Optional
from ..protocol.ydis import YDISProtocol
from ..protocol.constants import (
    YDIS_CMD_READ_MAP_CALIBRATION,
    YDIS_CMD_SET_CO_TRIM,
)
from ..models.map_tables import ECUMappingProfile, MapTable3D
from ..core.exceptions import MappingReadError


class MappingService:
    """Service to handle Yamaha ECU mapping calibration, CO tuning, and table analysis."""

    def __init__(self, protocol: YDISProtocol):
        self.protocol = protocol
        self.active_profile: ECUMappingProfile = ECUMappingProfile.create_default_mio_gt()

    def read_co_trim(self) -> int:
        """
        Reads active CO (Carbon Monoxide) fuel enrichment trim from ECU EEPROM.
        Return value ranges from -30 to +30.
        """
        resp_id, payload = self.protocol.send_command(YDIS_CMD_READ_MAP_CALIBRATION)
        # resp_id is 0x63, payload: [CO_TRIM + 128] [RPM_LIM_HI] [RPM_LIM_LO]
        if len(payload) >= 1:
            raw_co = payload[0]
            co_trim = raw_co - 128
            self.active_profile.co_adjustment_trim = co_trim
            return co_trim
        raise MappingReadError("Gagal membaca nilai CO Trim dari ECU.")

    def set_co_trim(self, trim_value: int) -> bool:
        """
        Sets CO fuel trim on Yamaha ECU (-30 to +30).
        - Value < 0 makes mixture leaner.
        - Value > 0 makes mixture richer.
        """
        if not (-30 <= trim_value <= 30):
            raise ValueError(f"Nilai CO trim harus antara -30 dan +30 (Diberikan: {trim_value})")

        raw_co = (trim_value + 128) & 0xFF
        resp_id, payload = self.protocol.send_command(YDIS_CMD_SET_CO_TRIM, bytes([raw_co]))
        if resp_id == 0x64 or (len(payload) >= 1 and payload[0] == raw_co):
            self.active_profile.co_adjustment_trim = trim_value
            return True
        return False

    def read_rpm_limiter(self) -> int:
        """
        Reads engine maximum RPM limiter configuration.
        """
        resp_id, payload = self.protocol.send_command(YDIS_CMD_READ_MAP_CALIBRATION)
        if len(payload) >= 3:
            limiter = (payload[1] << 8) | payload[2]
            self.active_profile.rpm_limiter_rpm = limiter
            return limiter
        return self.active_profile.rpm_limiter_rpm

    def load_profile_from_json(self, file_path: str) -> ECUMappingProfile:
        """Loads complete ECU fuel & ignition mapping from a JSON definition file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        profile = ECUMappingProfile(
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
            profile.fuel_map = MapTable3D(
                name=fm["name"],
                description=fm["description"],
                rpm_axis=fm["rpm_axis"],
                load_axis=fm["load_axis"],
                load_axis_name=fm["load_axis_name"],
                matrix=fm["matrix"],
                unit=fm["unit"],
            )

        if "ignition_map" in data and data["ignition_map"]:
            im = data["ignition_map"]
            profile.ignition_map = MapTable3D(
                name=im["name"],
                description=im["description"],
                rpm_axis=im["rpm_axis"],
                load_axis=im["load_axis"],
                load_axis_name=im["load_axis_name"],
                matrix=im["matrix"],
                unit=im["unit"],
            )

        self.active_profile = profile
        return profile

    def export_profile_to_json(self, file_path: str) -> None:
        """Saves current mapping tables to a JSON file."""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.active_profile.to_json())

    def export_map_to_csv(self, map_table: MapTable3D, file_path: str) -> None:
        """Exports a 3D table (Fuel or Ignition) to spreadsheet-friendly CSV format."""
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Header row: Load axis name followed by RPM columns
            writer.writerow([f"{map_table.load_axis_name} \\ RPM"] + map_table.rpm_axis)
            for row_idx, load_val in enumerate(map_table.load_axis):
                row_data = [load_val] + map_table.matrix[row_idx]
                writer.writerow(row_data)

    def apply_fuel_trim_percentage(self, percentage: float) -> None:
        """
        Applies a global percentage trim to the entire fuel injection matrix.
        E.g. +5.0 adds 5% fuel across all cells.
        """
        if not self.active_profile.fuel_map:
            return
        factor = 1.0 + (percentage / 100.0)
        for r_idx in range(len(self.active_profile.fuel_map.matrix)):
            for c_idx in range(len(self.active_profile.fuel_map.matrix[r_idx])):
                curr = self.active_profile.fuel_map.matrix[r_idx][c_idx]
                self.active_profile.fuel_map.matrix[r_idx][c_idx] = round(curr * factor, 2)
