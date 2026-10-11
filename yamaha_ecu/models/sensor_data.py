"""
Sensor and live telemetry data models for Yamaha Mio GT 2015.
Represents RPS (Revolutions Per Second/Minute), throttle, pressures, temperatures, and timings.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any


@dataclass
class SensorData:
    timestamp: float
    engine_speed_rpm: int          # RPM (Engine Putaran Mesin)
    engine_speed_rps: float        # RPS (Revolutions Per Second = RPM / 60)
    throttle_position_pct: float   # TPS % (0.0% to 100.0%)
    throttle_angle_deg: float      # Throttle angle in degrees (approx 0 - 85 deg)
    throttle_voltage_v: float      # TPS Voltage (0.5V to 4.5V)
    engine_temp_c: float           # Engine / Cylinder Head Temperature (°C)
    intake_air_temp_c: float       # IAT (°C)
    manifold_pressure_kpa: float   # MAP (Intake manifold air pressure, kPa)
    atmospheric_pressure_kpa: float# Barometric pressure (kPa)
    battery_voltage_v: float       # Battery/System voltage (V)
    o2_sensor_voltage_v: float     # O2 Lambda Sensor (0.0V - 1.0V)
    o2_lambda: float               # Estimated Lambda / Air-Fuel Ratio equivalence
    injector_pulse_width_ms: float # Fuel Injection duration (ms)
    ignition_advance_deg: float    # Ignition timing BTDC (degrees Before Top Dead Center)
    isc_valve_steps: int           # Idle Speed Control actuator step (0 - 120 steps)
    gear_neutral: bool             # Neutral/Clutch status
    kickstand_down: bool           # Side-stand switch state
    tip_over_sensor_v: float       # Lean angle voltage (1.4V normal)
    fuel_consumption_l_per_h: float# Calculated L/h consumption

    @classmethod
    def from_raw_bytes(cls, raw: bytes, timestamp: float = None) -> "SensorData":
        """
        Parse raw Yamaha Y-DIS Live Data telemetry frame.
        Standard Y-DIS mode 0x21 payload structure (e.g. 18-24 bytes payload):
        Byte 0-1: RPM (2 bytes big endian)
        Byte 2: TPS raw (0-255 -> 0-100%)
        Byte 3: Engine Temp raw (offset -40°C)
        Byte 4: IAT raw (offset -40°C)
        Byte 5: MAP pressure raw (kPa)
        Byte 6: Atmospheric pressure (kPa)
        Byte 7: Battery voltage (x 0.1 V)
        Byte 8: O2 Sensor voltage (x 0.005 V or raw ADC)
        Byte 9-10: Injector pulse width (microseconds, x 0.01 ms)
        Byte 11: Ignition advance BTDC (offset -10 deg or direct)
        Byte 12: ISC Valve step
        Byte 13: Bitmask flags (Kickstand, Neutral, Tip-over)
        """
        import time
        ts = timestamp if timestamp is not None else time.time()

        if len(raw) < 14:
            raise ValueError(f"Raw telemetry payload too short: {len(raw)} bytes (expected >= 14)")

        # Byte 0-1: Engine RPM
        rpm = (raw[0] << 8) | raw[1]
        rps = round(rpm / 60.0, 2)

        # Byte 2: TPS (0 = 0%, 255 = 100%)
        tps_raw = raw[2]
        tps_pct = round((tps_raw / 255.0) * 100.0, 1)
        tps_deg = round(tps_pct * 0.85, 1)
        tps_v = round(0.5 + (tps_pct / 100.0) * 4.0, 2)

        # Byte 3: Engine Temperature (°C = raw - 40)
        eng_temp = float(raw[3] - 40)

        # Byte 4: Intake Air Temperature (°C = raw - 40)
        iat_temp = float(raw[4] - 40)

        # Byte 5: Intake Manifold Pressure (kPa)
        map_kpa = float(raw[5])

        # Byte 6: Barometric pressure (kPa)
        baro_kpa = float(raw[6]) if raw[6] > 0 else 101.3

        # Byte 7: Battery Voltage (0.1V per tick)
        vbat = round(raw[7] * 0.1, 2)

        # Byte 8: O2 Sensor Voltage (0-255 -> 0.0 - 1.0V)
        o2_v = round((raw[8] / 255.0) * 1.0, 3)
        # Approximate lambda: 0.45V is stoichiometric (1.0)
        o2_lambda = round(1.0 + (0.45 - o2_v) * 0.5, 2)

        # Byte 9-10: Injector Pulse Width (0.01 ms per tick)
        inj_raw = (raw[9] << 8) | raw[10]
        inj_ms = round(inj_raw * 0.01, 2)

        # Byte 11: Ignition Timing (BTDC in degrees, offset typically -10)
        ign_deg = float(raw[11] - 10)

        # Byte 12: ISC Valve Steps
        isc_steps = int(raw[12])

        # Byte 13: Bitmask status flags
        flags = raw[13]
        neutral = bool(flags & 0x01)
        kickstand = bool(flags & 0x02)
        tip_over_v = 1.4 if not bool(flags & 0x04) else 4.0

        # Calculated fuel consumption (approximate single cylinder 113cc at RPM with pulse width)
        # Flow rate ~ 120cc/min = 2cc/sec injector
        cc_per_sec = (inj_ms / 1000.0) * (rpm / 2.0 / 60.0) * 2.0
        fuel_lh = round(cc_per_sec * 3.6, 2)

        return cls(
            timestamp=ts,
            engine_speed_rpm=rpm,
            engine_speed_rps=rps,
            throttle_position_pct=tps_pct,
            throttle_angle_deg=tps_deg,
            throttle_voltage_v=tps_v,
            engine_temp_c=eng_temp,
            intake_air_temp_c=iat_temp,
            manifold_pressure_kpa=map_kpa,
            atmospheric_pressure_kpa=baro_kpa,
            battery_voltage_v=vbat,
            o2_sensor_voltage_v=o2_v,
            o2_lambda=o2_lambda,
            injector_pulse_width_ms=inj_ms,
            ignition_advance_deg=ign_deg,
            isc_valve_steps=isc_steps,
            gear_neutral=neutral,
            kickstand_down=kickstand,
            tip_over_sensor_v=tip_over_v,
            fuel_consumption_l_per_h=fuel_lh,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary."""
        d = asdict(self)
        d["formatted_time"] = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S.%f")[:-3]
        return d
