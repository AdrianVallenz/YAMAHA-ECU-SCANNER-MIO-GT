#!/usr/bin/env python3
"""
Launcher Script for Yamaha ECU Real-Time Visual Dashboard & Telemetry Studio.
Target: Yamaha Mio GT 2015 115cc YMJET-FI (ECU 54P-H591A-00 / 2BJ).

Usage:
    python visual_dashboard.py                  # Runs with virtual ECU simulator (Mock)
    python visual_dashboard.py --serial COM3    # Connects to physical K-Line USB cable
    python visual_dashboard.py --port 8080      # Custom web port
"""

import sys
import argparse
from yamaha_ecu.web.server import start_web_server


def main():
    parser = argparse.ArgumentParser(
        description="Yamaha ECU Visual Dashboard & Telemetry Studio (Yamaha Mio GT 2015)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port web server lokal (default: 8000)",
    )
    parser.add_argument(
        "--serial",
        type=str,
        default=None,
        help="COM Port fisik K-Line (contoh: COM3, /dev/ttyUSB0). Jika diabaikan, simulator mock aktif.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=10400,
        help="Baud rate Y-DIS K-Line (default: 10400)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Jangan buka browser secara otomatis",
    )
    args = parser.parse_args()

    use_mock = args.serial is None
    port_name = args.serial if args.serial else "COM3"

    start_web_server(
        port=args.port,
        mock=use_mock,
        serial_port=port_name,
        baudrate=args.baud,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
