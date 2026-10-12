"""
Offline Visual Plotter for Yamaha ECU Telemetry and Maps using Matplotlib.
Renders high-resolution multi-panel telemetry graphs and 3D ECU surface plots.
"""

import os
import csv
from typing import Optional, List, Dict
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import cm
from .models.map_tables import ECUMappingProfile


def plot_telemetry_csv(
    csv_path: str,
    save_image_path: Optional[str] = None,
    show_plot: bool = False,
) -> str:
    """
    Parses recorded CSV telemetry and plots 4-panel diagnostic dashboard.
    Returns the path to the saved image.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Telemetry CSV file not found: {csv_path}")

    # Read CSV data
    rows = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if not rows:
        raise ValueError("CSV telemetry file is empty.")

    # Parse numeric series
    timestamps = []
    rpms = []
    rpss = []
    tpss = []
    eng_temps = []
    iat_temps = []
    map_kpas = []
    vbats = []
    inj_mss = []
    ign_degs = []

    t0 = float(rows[0].get("timestamp", 0))
    for r in rows:
        t = float(r.get("timestamp", 0)) - t0
        timestamps.append(t)
        rpms.append(float(r.get("engine_speed_rpm", 0)))
        rpss.append(float(r.get("engine_speed_rps", 0)))
        tpss.append(float(r.get("throttle_position_pct", 0)))
        eng_temps.append(float(r.get("engine_temp_c", 0)))
        iat_temps.append(float(r.get("intake_air_temp_c", 0)))
        map_kpas.append(float(r.get("manifold_pressure_kpa", 0)))
        vbats.append(float(r.get("battery_voltage_v", 0)))
        inj_mss.append(float(r.get("injector_pulse_width_ms", 0)))
        ign_degs.append(float(r.get("ignition_advance_deg", 0)))

    # Dark theme automotive styling
    plt.style.use("dark_background")
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f"Yamaha Mio GT 2015 - Telemetry Analysis: {os.path.basename(csv_path)}", fontsize=14, fontweight="bold", color="#00f0ff")

    # 1. RPM & RPS
    ax1 = axes[0]
    ax1.plot(timestamps, rpms, color="#00f0ff", label="RPM (Putaran Mesin)", linewidth=1.5)
    ax1.axhline(9500, color="#ff3366", linestyle="--", alpha=0.7, label="Redline 9500 RPM")
    ax1.set_ylabel("RPM", color="#00f0ff", fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.4)
    ax1.legend(loc="upper right")

    # RPS secondary y-axis
    ax1_rps = ax1.twinx()
    ax1_rps.plot(timestamps, rpss, color="#a371f7", linestyle=":", alpha=0.5, label="RPS")
    ax1_rps.set_ylabel("RPS (Hz)", color="#a371f7")

    # 2. Throttle TPS & MAP
    ax2 = axes[1]
    ax2.plot(timestamps, tpss, color="#ffaa00", label="TPS % (Bukaan Gas)", linewidth=1.5)
    ax2.set_ylabel("TPS (%)", color="#ffaa00", fontweight="bold")
    ax2.set_ylim(-5, 105)
    ax2.grid(True, linestyle=":", alpha=0.4)

    ax2_map = ax2.twinx()
    ax2_map.plot(timestamps, map_kpas, color="#00e676", linestyle="-.", label="MAP (kPa)", linewidth=1.2)
    ax2_map.set_ylabel("MAP (kPa)", color="#00e676")
    ax2.legend(loc="upper left")
    ax2_map.legend(loc="upper right")

    # 3. Engine Temperature & Intake Air Temp
    ax3 = axes[2]
    ax3.plot(timestamps, eng_temps, color="#ff5722", label="Engine Temp ECT (°C)", linewidth=1.5)
    ax3.plot(timestamps, iat_temps, color="#03a9f4", label="Intake Temp IAT (°C)", linewidth=1.2)
    ax3.set_ylabel("Temp (°C)", fontweight="bold")
    ax3.grid(True, linestyle=":", alpha=0.4)
    ax3.legend(loc="upper right")

    # 4. Injector Pulse Width & Ignition Advance
    ax4 = axes[3]
    ax4.plot(timestamps, inj_mss, color="#ffeb3b", label="Inj Duration (ms)", linewidth=1.5)
    ax4.set_ylabel("Injektor (ms)", color="#ffeb3b", fontweight="bold")
    ax4.grid(True, linestyle=":", alpha=0.4)

    ax4_ign = ax4.twinx()
    ax4_ign.plot(timestamps, ign_degs, color="#e91e63", linestyle="--", label="Ignition (°BTDC)", linewidth=1.2)
    ax4_ign.set_ylabel("Ignition (°BTDC)", color="#e91e63")
    ax4.set_xlabel("Waktu (Detik)", fontweight="bold")
    ax4.legend(loc="upper left")
    ax4_ign.legend(loc="upper right")

    plt.tight_layout()

    out_file = save_image_path or csv_path.replace(".csv", "_analysis.png")
    plt.savefig(out_file, dpi=150)
    if show_plot:
        plt.show()
    plt.close(fig)
    return out_file


def plot_ecu_maps(
    profile: Optional[ECUMappingProfile] = None,
    save_image_path: Optional[str] = None,
    show_plot: bool = False,
) -> str:
    """
    Generates 2D heatmaps and 3D surface visualizations of Fuel and Ignition Maps.
    """
    if profile is None:
        profile = ECUMappingProfile.create_default_mio_gt()

    plt.style.use("dark_background")
    fig = plt.figure(figsize=(14, 6))

    # Fuel Map 2D Heatmap
    fuel = profile.fuel_map
    ax1 = fig.add_subplot(1, 2, 1)
    im1 = ax1.imshow(
        fuel.matrix,
        cmap="turbo",
        aspect="auto",
        origin="lower",
    )
    ax1.set_title("Yamaha Mio GT 115 - Main Fuel Map (ms)", fontsize=12, fontweight="bold", color="#00f0ff")
    ax1.set_xticks(range(len(fuel.rpm_axis)))
    ax1.set_xticklabels([str(r) for r in fuel.rpm_axis], rotation=45)
    ax1.set_yticks(range(len(fuel.load_axis)))
    ax1.set_yticklabels([f"{t:.0f}%" for t in fuel.load_axis])
    ax1.set_xlabel("RPM")
    ax1.set_ylabel("Bukaan Gas (TPS %)")
    fig.colorbar(im1, ax=ax1, label="Pulse Width (ms)")

    # Ignition Map 2D Heatmap
    ign = profile.ignition_map
    ax2 = fig.add_subplot(1, 2, 2)
    im2 = ax2.imshow(
        ign.matrix,
        cmap="viridis",
        aspect="auto",
        origin="lower",
    )
    ax2.set_title("Yamaha Mio GT 115 - Base Ignition Timing (°BTDC)", fontsize=12, fontweight="bold", color="#ffaa00")
    ax2.set_xticks(range(len(ign.rpm_axis)))
    ax2.set_xticklabels([str(r) for r in ign.rpm_axis], rotation=45)
    ax2.set_yticks(range(len(ign.load_axis)))
    ax2.set_yticklabels([f"{t:.0f}%" for t in ign.load_axis])
    ax2.set_xlabel("RPM")
    ax2.set_ylabel("Bukaan Gas (TPS %)")
    fig.colorbar(im2, ax=ax2, label="Advance (°BTDC)")

    plt.tight_layout()
    out_file = save_image_path or "yamaha_mio_gt_maps_visual.png"
    plt.savefig(out_file, dpi=150)
    if show_plot:
        plt.show()
    plt.close(fig)
    return out_file
