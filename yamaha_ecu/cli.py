"""
Command Line Interface (CLI) for Yamaha ECU Diagnostic & Mapping Framework.
Optimized for Yamaha Mio GT 2015 (54P / 2BJ Engine Control Unit).
"""

import sys
import time
import argparse
from typing import Optional
from .core.ecu_client import YamahaECUClient
from .hardware.serial_kline import SerialKLineAdapter
from .hardware.mock_adapter import MockKLineAdapter


def get_client(args: argparse.Namespace) -> YamahaECUClient:
    """Helper to initialize client based on CLI arguments."""
    if args.mock:
        adapter = MockKLineAdapter()
    else:
        adapter = SerialKLineAdapter(port=args.port, baudrate=args.baud)
    return YamahaECUClient(hardware=adapter)


def cmd_read_dtc(args: argparse.Namespace) -> None:
    print(f"\n[+] Menghubungkan ke ECU Yamaha Mio GT ({'MODE SIMULATOR' if args.mock else args.port})...")
    with get_client(args) as ecu:
        active, history = ecu.diagnostic.read_dtc()

        print("=" * 70)
        print("          HASIL DIAGNOSA KODE KERUSAKAN (DTC) YAMAHA MIO GT 2015")
        print("=" * 70)

        print(f"\n[-] KODE KERUSAKAN AKTIF (MALFUNCTION AKTIF): {len(active)} ditemukan")
        if active:
            for item in active:
                print(f"  * [KODE {item.code:02d}] {item.name}")
                print(f"    - Deskripsi : {item.description}")
                print(f"    - Gejala    : {item.symptoms}")
                print(f"    - Penyebab  : {item.probable_cause}")
        else:
            print("  -> Tidak ada kode kerusakan aktif. Sistem FI normal.")

        print(f"\n[-] KODE KERUSAKAN HISTORIS (RIWAYAT MEMORI): {len(history)} ditemukan")
        if history:
            for item in history:
                print(f"  * [KODE {item.code:02d}] {item.name}")
                print(f"    - Deskripsi : {item.description}")
        else:
            print("  -> Tidak ada riwayat kerusakan di memori EEPROM.")
        print("=" * 70 + "\n")


def cmd_clear_dtc(args: argparse.Namespace) -> None:
    print(f"\n[+] Menghapus riwayat kerusakan di ECU Yamaha ({'SIMULATOR' if args.mock else args.port})...")
    with get_client(args) as ecu:
        success = ecu.diagnostic.clear_dtc()
        if success:
            print("[v] Berhasil! Seluruh kode kerusakan (DTC) pada EEPROM berhasil di-reset.")
        else:
            print("[x] Gagal mereset kode kerusakan. Pastikan kontak ON dan mesin dalam keadaan mati.")


def cmd_live_rps(args: argparse.Namespace) -> None:
    print(f"\n[+] Memulai streaming telemetry RPS / Live Data ({'SIMULATOR' if args.mock else args.port})...")
    print("[i] Tekan Ctrl+C untuk berhenti.\n")
    print(f"{'TIME':<10} | {'RPM':<6} | {'RPS':<6} | {'TPS %':<6} | {'ENG °C':<6} | {'IAT °C':<6} | {'MAP kPa':<7} | {'VBAT V':<6} | {'INJ ms':<6} | {'IGN °':<5}")
    print("-" * 88)

    with get_client(args) as ecu:
        try:
            while True:
                data = ecu.live_data.read_snapshot()
                t_str = time.strftime("%H:%M:%S")
                print(
                    f"{t_str:<10} | "
                    f"{data.engine_speed_rpm:<6} | "
                    f"{data.engine_speed_rps:<6.1f} | "
                    f"{data.throttle_position_pct:<6.1f} | "
                    f"{data.engine_temp_c:<6.1f} | "
                    f"{data.intake_air_temp_c:<6.1f} | "
                    f"{data.manifold_pressure_kpa:<7.1f} | "
                    f"{data.battery_voltage_v:<6.2f} | "
                    f"{data.injector_pulse_width_ms:<6.2f} | "
                    f"{data.ignition_advance_deg:<5.1f}"
                )
                time.sleep(args.interval / 1000.0)
        except KeyboardInterrupt:
            print("\n[!] Streaming dihentikan oleh pengguna.")


def cmd_diag_sensors(args: argparse.Namespace) -> None:
    print(f"\n[+] Menjalankan inspeksi sensor DIAG Mode (d01-d70) ({'SIMULATOR' if args.mock else args.port})...")
    with get_client(args) as ecu:
        results = ecu.diagnostic.run_all_sensor_diagnostics()

        print("=" * 65)
        print("          HASIL DIAGNOSTIC MODE (DIAG CODE INSPECTION)")
        print("=" * 65)
        for res in results:
            status = "[NORMAL]" if res["in_range"] else "[PERIKSA]"
            print(f"  {status:<9} {res['name']:<42} : {res['value']} {res['unit']}")
        print("=" * 65 + "\n")


def cmd_view_mapping(args: argparse.Namespace) -> None:
    print(f"\n[+] Membaca profil Mapping & Kalibrasi ECU Mio GT ({'SIMULATOR' if args.mock else args.port})...")
    with get_client(args) as ecu:
        co = ecu.mapping.read_co_trim()
        limiter = ecu.mapping.read_rpm_limiter()
        profile = ecu.mapping.active_profile

        print("=" * 70)
        print("                PROFIL MAPPING ECU YAMAHA MIO GT 2015")
        print("=" * 70)
        print(f"  * Model Motor       : {profile.model_name}")
        print(f"  * Kode Part ECU     : {profile.ecu_part_number}")
        print(f"  * Versi Firmware    : {profile.firmware_version}")
        print(f"  * RPM Limiter       : {limiter} RPM")
        print(f"  * Target Idling     : {profile.idle_target_warm_rpm} RPM (Dingin: {profile.idle_target_cold_rpm} RPM)")
        print(f"  * CO Trim Setting   : {co} (Rentang: -30 s/d +30)")
        print("-" * 70)

        if profile.fuel_map:
            fm = profile.fuel_map
            print(f"\n[+] {fm.name} ({fm.unit}):")
            header = f"{fm.load_axis_name:<10} | " + " | ".join(f"{r:>5}" for r in fm.rpm_axis)
            print(header)
            print("-" * len(header))
            for row_idx, load_val in enumerate(fm.load_axis):
                row_str = f"{load_val:>8.1f}% | " + " | ".join(f"{val:>5.2f}" for val in fm.matrix[row_idx])
                print(row_str)

        if profile.ignition_map:
            im = profile.ignition_map
            print(f"\n[+] {im.name} ({im.unit}):")
            header = f"{im.load_axis_name:<10} | " + " | ".join(f"{r:>5}" for r in im.rpm_axis)
            print(header)
            print("-" * len(header))
            for row_idx, load_val in enumerate(im.load_axis):
                row_str = f"{load_val:>8.1f}% | " + " | ".join(f"{val:>5.1f}" for val in im.matrix[row_idx])
                print(row_str)

        print("=" * 70 + "\n")


def cmd_set_co(args: argparse.Namespace) -> None:
    val = args.value
    print(f"\n[+] Mengubah nilai setelan CO menjadi {val}...")
    with get_client(args) as ecu:
        success = ecu.mapping.set_co_trim(val)
        if success:
            print(f"[v] Berhasil! Nilai CO trim ECU tersimpan: {val}")
        else:
            print("[x] Gagal menyimpan nilai CO. Pastikan kontak ON dan ECU merespon.")


def cmd_export_map(args: argparse.Namespace) -> None:
    with get_client(args) as ecu:
        out_json = args.output or "yamaha_mio_gt_map.json"
        ecu.mapping.export_profile_to_json(out_json)
        print(f"[v] Berhasil mengekspor profil mapping ke file: {out_json}")


def cmd_web(args: argparse.Namespace) -> None:
    from .web.server import start_web_server
    start_web_server(
        port=args.web_port,
        mock=args.mock,
        serial_port=args.port,
        baudrate=args.baud,
        open_browser=not args.no_browser,
    )


def cmd_plot(args: argparse.Namespace) -> None:
    from .plotter import plot_telemetry_csv, plot_ecu_maps
    if args.file:
        out = plot_telemetry_csv(args.file, save_image_path=args.output, show_plot=args.show)
        print(f"[v] Grafik analisis telemetri berhasil disimpan: {out}")
    else:
        out = plot_ecu_maps(save_image_path=args.output, show_plot=args.show)
        print(f"[v] Visualisasi peta matriks ECU berhasil disimpan: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Framework Diagnosa, Live Telemetri (RPS), dan Mapping ECU Yamaha Mio GT 2015"
    )
    parser.add_argument("--port", default="COM3", help="Port Serial K-Line (misal: COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=10400, help="Baudrate K-Line (default: 10400)")
    parser.add_argument("--mock", action="store_true", help="Gunakan mode simulator virtual ECU (tanpa motor)")

    subparsers = parser.add_subparsers(dest="command", help="Perintah yang tersedia")

    # DTC command
    subparsers.add_parser("dtc", help="Baca kode kerusakan mesin (aktif dan historis)")

    # Clear DTC command
    subparsers.add_parser("clear-dtc", help="Hapus riwayat kode kerusakan di ECU")

    # Live RPS command
    p_rps = subparsers.add_parser("rps", help="Baca putaran mesin (RPM & RPS) dan streaming sensor live")
    p_rps.add_argument("--interval", type=int, default=150, help="Interval pembacaan dalam milidetik (default: 150)")

    # DIAG command
    subparsers.add_parser("diag", help="Inspeksi parameter sensor kode diagnostik (d01-d70)")

    # Mapping command
    subparsers.add_parser("mapping", help="Tampilkan tabel kalibrasi mapping bahan bakar & pengapian")

    # Set CO command
    p_co = subparsers.add_parser("set-co", help="Atur nilai CO adjustment (-30 s/d +30)")
    p_co.add_argument("value", type=int, help="Nilai CO trim yang diinginkan (-30 sampai +30)")

    # Export map command
    p_exp = subparsers.add_parser("export-map", help="Ekspor tabel mapping ke format file JSON")
    p_exp.add_argument("--output", default="yamaha_mio_gt_map.json", help="Nama file tujuan ekspor")

    # Web Dashboard command
    p_web = subparsers.add_parser("web", help="Buka dashboard visual interaktif berbasis web (Browser)")
    p_web.add_argument("--web-port", type=int, default=8000, help="Port server HTTP (default: 8000)")
    p_web.add_argument("--no-browser", action="store_true", help="Jangan buka browser secara otomatis")

    # Plot offline command
    p_plot = subparsers.add_parser("plot", help="Buat grafik visual data telemetri CSV atau peta ECU")
    p_plot.add_argument("--file", type=str, default=None, help="Path ke file log CSV telemetri")
    p_plot.add_argument("--output", type=str, default=None, help="Path file output gambar PNG")
    p_plot.add_argument("--show", action="store_true", help="Tampilkan jendela plot interaktif")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "dtc": cmd_read_dtc,
        "clear-dtc": cmd_clear_dtc,
        "rps": cmd_live_rps,
        "diag": cmd_diag_sensors,
        "mapping": cmd_view_mapping,
        "set-co": cmd_set_co,
        "export-map": cmd_export_map,
        "web": cmd_web,
        "plot": cmd_plot,
    }

    handler = dispatch.get(args.command)
    if handler:
        try:
            handler(args)
        except Exception as e:
            print(f"\n[ERROR] Operasi gagal: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
