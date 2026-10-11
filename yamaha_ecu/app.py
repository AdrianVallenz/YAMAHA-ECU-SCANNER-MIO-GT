"""
Interactive Real-Time Terminal Dashboard for Yamaha ECU Telemetry (RPS & Sensors).
Displays ASCII rev meters, gauges, and status flags.
"""

import os
import sys
import time
import argparse
from .core.ecu_client import YamahaECUClient
from .hardware.serial_kline import SerialKLineAdapter
from .hardware.mock_adapter import MockKLineAdapter


def draw_bar(value: float, max_val: float, width: int = 30, char: str = "#") -> str:
    """Renders a progress bar string."""
    filled = int(min(1.0, max(0.0, value / max_val)) * width)
    return f"[{char * filled}{' ' * (width - filled)}]"


def run_dashboard(client: YamahaECUClient, refresh_hz: float = 10.0) -> None:
    delay = 1.0 / refresh_hz
    clear_cmd = "cls" if os.name == "nt" else "clear"

    print("Memulai koneksi ke ECU Yamaha Mio GT 2015...")
    with client as ecu:
        active_dtcs, _ = ecu.diagnostic.read_dtc()

        try:
            while True:
                data = ecu.live_data.read_snapshot()
                os.system(clear_cmd)

                print("=" * 72)
                print("     YAMAHA MOTORCYCLE REAL-TIME ECU TELEMETRY DASHBOARD (Y-DIS)")
                print("           Target: Yamaha Mio GT 2015 115cc YMJET-FI (54P/2BJ)")
                print("=" * 72)

                # Engine Speed (RPM & RPS)
                rpm_bar = draw_bar(data.engine_speed_rpm, 9500, width=35, char="█")
                print(f" PUTARAN MESIN (RPM) : {data.engine_speed_rpm:>5} RPM  {rpm_bar}")
                rps_bar = draw_bar(data.engine_speed_rps, 160, width=35, char="▓")
                print(f" FREKUENSI MESIN (RPS): {data.engine_speed_rps:>5.1f} RPS  {rps_bar}")

                print("-" * 72)

                # Throttle (TPS)
                tps_bar = draw_bar(data.throttle_position_pct, 100.0, width=35, char="■")
                print(f" BUKAAN GAS (TPS)    : {data.throttle_position_pct:>5.1f} %    {tps_bar} ({data.throttle_voltage_v:.2f}V)")

                # Intake Manifold Pressure (MAP)
                map_bar = draw_bar(data.manifold_pressure_kpa, 110.0, width=35, char="■")
                print(f" TEKANAN INTAKE (MAP): {data.manifold_pressure_kpa:>5.1f} kPa  {map_bar}")

                # Engine Temperature
                temp_bar = draw_bar(data.engine_temp_c, 120.0, width=35, char="■")
                print(f" SUHU MESIN (CYL/ECT): {data.engine_temp_c:>5.1f} °C   {temp_bar}")

                # Airbox Temperature (IAT)
                iat_bar = draw_bar(data.intake_air_temp_c, 60.0, width=35, char="■")
                print(f" SUHU UDARA INTAKE   : {data.intake_air_temp_c:>5.1f} °C   {iat_bar}")

                print("-" * 72)

                # Powertrain & Electrical Parameters
                print(f" TEGANGAN AKI (VBAT) : {data.battery_voltage_v:>5.2f} V     |  SENSOR O2 VOLT : {data.o2_sensor_voltage_v:.3f} V")
                print(f" DURASI INJEKTOR     : {data.injector_pulse_width_ms:>5.2f} ms    |  ESTIMASI LAMBDA: {data.o2_lambda:.2f} λ")
                print(f" DERAJAT PENGAPIAN   : {data.ignition_advance_deg:>5.1f} °BTDC |  KATUP ISC STEP : {data.isc_valve_steps} steps")
                print(f" KONSUMSI BBM        : {data.fuel_consumption_l_per_h:>5.2f} L/Jam  |  SENSOR KEMIRING: {data.tip_over_sensor_v:.2f} V")

                print("-" * 72)

                # Diagnostic Status Banner
                if active_dtcs:
                    dtc_str = ", ".join(f"KODE {d.code}" for d in active_dtcs)
                    print(f" STATUS MALFUNCTION  : [PERINGATAN] Terdeteksi Kerusakan: {dtc_str}")
                else:
                    print(" STATUS MALFUNCTION  : [NORMAL] Tidak ada kode kerusakan (MIL OFF)")

                print("=" * 72)
                print(" Tekan [Ctrl+C] untuk keluar dari live dashboard.")

                time.sleep(delay)

        except KeyboardInterrupt:
            print("\nDashboard ditutup.")


def main():
    parser = argparse.ArgumentParser(description="Live Dashboard Telemetri Yamaha ECU")
    parser.add_argument("--port", default="COM3", help="Serial port")
    parser.add_argument("--baud", type=int, default=10400, help="Baud rate")
    parser.add_argument("--mock", action="store_true", help="Gunakan mock simulator")
    parser.add_argument("--hz", type=float, default=8.0, help="Refresh rate (Hz)")
    args = parser.parse_args()

    adapter = MockKLineAdapter() if args.mock else SerialKLineAdapter(port=args.port, baudrate=args.baud)
    client = YamahaECUClient(hardware=adapter)
    run_dashboard(client, refresh_hz=args.hz)


if __name__ == "__main__":
    main()
