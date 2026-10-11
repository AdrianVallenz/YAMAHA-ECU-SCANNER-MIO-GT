"""
Yamaha Diagnostic Trouble Code (DTC) models and definitions.
Optimized for Yamaha Mio GT (2015) 115cc YMJET-FI (ECU 54P / 2BJ series).
"""

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class DTCFault:
    code: int
    name: str
    description: str
    symptoms: str
    probable_cause: str
    is_active: bool = True
    occurrence_count: int = 1

    def __str__(self) -> str:
        status = "AKTIF" if self.is_active else "HISTORIS"
        return f"[DTC {self.code:02d}] {self.name} ({status}): {self.description}"


# Standard Yamaha FI DTC Table for Mio GT (54P / 2BJ)
YAMAHA_MIO_GT_DTC_MAP: Dict[int, Dict[str, str]] = {
    12: {
        "name": "Crankshaft Position Sensor (Pulser Coil)",
        "description": "Tidak ada sinyal normal yang diterima dari sensor posisi crankshaft (pulser).",
        "symptoms": "Mesin tidak dapat dihidupkan (tidak ada percikan api/injeksi bahan bakar).",
        "probable_cause": "Sensor pulser rusak, kabel pulser putus/konslet, atau spull bermasalah.",
    },
    13: {
        "name": "Intake Air Pressure Sensor (Open/Short)",
        "description": "Tegangan output sensor tekanan udara masuk (MAP) di luar rentang normal (<0.20V atau >4.80V).",
        "symptoms": "Mesin tersendat pada akselerasi, idling kasar, emisi gas buang memburuk.",
        "probable_cause": "Sensor MAP rusak, soket kendor, kabel putus atau terhubung ke ground.",
    },
    14: {
        "name": "Intake Air Pressure Hose Malfunction",
        "description": "Sinyal sensor MAP tidak sinkron dengan kondisi bukaan throttle (kebocoran vakum).",
        "symptoms": "Idling tidak stabil, tarikan berat, mesin bisa mati mendadak.",
        "probable_cause": "Selang vakum ke intake manifold copot, robek, terjepit, atau tersumbat.",
    },
    15: {
        "name": "Throttle Position Sensor (TPS Open/Short)",
        "description": "Tegangan output sensor bukaan gas (TPS) di luar batas standar (<0.20V atau >4.80V).",
        "symptoms": "Respon gas lambat, brebet saat ditarik, tidak bisa deselerasi halus.",
        "probable_cause": "Sensor TPS aus/rusak, jalur kabel 5V/Ground/Signal putus atau konslet.",
    },
    16: {
        "name": "Throttle Position Sensor (Stuck)",
        "description": "Sensor TPS mendeteksi nilai macet (tidak berubah saat putaran mesin naik/turun).",
        "symptoms": "Idling terlalu tinggi atau mesin brebet di putaran menengah.",
        "probable_cause": "Mekanisme katup throttle macet, sensor TPS bergeser/terjepit.",
    },
    21: {
        "name": "Coolant / Engine Temperature Sensor",
        "description": "Tegangan sensor suhu mesin (ECT / Cylinder Temp) terbuka atau konslet.",
        "symptoms": "Susah distarter saat mesin dingin, boros bensin, busi hitam.",
        "probable_cause": "Sensor suhu mesin rusak, soket sensor kotor/lepas, kabel terputus.",
    },
    22: {
        "name": "Intake Air Temperature Sensor (IAT)",
        "description": "Sinyal suhu udara intake di filter/airbox terputus atau korslet.",
        "symptoms": "Koreksi campuran bahan bakar kurang presisi di cuaca dingin/panas.",
        "probable_cause": "Sensor IAT di box filter rusak atau soket terlepas.",
    },
    24: {
        "name": "O2 Sensor Malfunction",
        "description": "Sinyal dari sensor O2 pada pipa knalpot tidak normal / tidak ada respons switching.",
        "symptoms": "Konsumsi bensin lebih boros, performa akselerasi menurun.",
        "probable_cause": "Sensor O2 kotor/rusak, kabel sensor terbakar knalpot, kebocoran paking knalpot.",
    },
    28: {
        "name": "Engine Temperature Sensor Signal Abnormal",
        "description": "Karakteristik kenaikan suhu mesin tidak sesuai kurva pemanasan standar.",
        "symptoms": "Pengapian dan suplai BBM tidak optimal selama fase pemanasan (warm-up).",
        "probable_cause": "Resistansi sensor suhu berubah drastis akibat panas berlebih (overheat).",
    },
    30: {
        "name": "Lean Angle Sensor (Motorcycle Overturned)",
        "description": "Sensor kemiringan mendeteksi sepeda motor terjatuh (>65 derajat).",
        "symptoms": "ECU otomatis memutus injeksi dan pengapian demi keamanan; motor mati.",
        "probable_cause": "Motor terjatuh, dudukan sensor kemiringan miring/terbalik, atau sensor rusak.",
    },
    33: {
        "name": "Ignition Coil Primary Lead Malfunction",
        "description": "Jalur primer koil pengapian terdeteksi putus atau hubungan singkat.",
        "symptoms": "Mesin mati tiba-tiba, tidak ada api di busi sama sekali.",
        "probable_cause": "Kabel oranye dari ECU ke koil putus, koil terbakar, atau transistor ECU rusak.",
    },
    39: {
        "name": "Fuel Injector Malfunction",
        "description": "Koil injektor bahan bakar terdeteksi putus (open) atau korslet.",
        "symptoms": "Bahan bakar tidak disemprotkan, mesin mogok.",
        "probable_cause": "Injektor terbakar, kabel injektor putus digigit tikus, atau konektor lepas.",
    },
    41: {
        "name": "Lean Angle Sensor (Open/Short)",
        "description": "Jalur kabel sensor sudut kemiringan terbuka atau konslet ke tegangan tinggi.",
        "symptoms": "Lampu MIL berkedip, mesin tidak bisa hidup.",
        "probable_cause": "Kabel sensor sudut putus atau soket terlepas.",
    },
    42: {
        "name": "Speed Sensor / Neutral Switch",
        "description": "Tidak ada sinyal kecepatan roda yang diterima ketika motor berjalan.",
        "symptoms": "Speedometer tidak bergerak, fungsi eco indicator tidak aktif.",
        "probable_cause": "Sensor speedometer di roda depan / girboks rusak atau kabel putus.",
    },
    44: {
        "name": "EEPROM Read/Write Error",
        "description": "Kesalahan memori non-volatile ECU saat membaca/menulis data CO adjustment.",
        "symptoms": "Setelan CO kembali ke default nol, performa motor berubah sewaktu-waktu.",
        "probable_cause": "Tegangan aki drop saat penyimpanan data, atau chip EEPROM internal ECU aus.",
    },
    46: {
        "name": "Vehicle Power Supply Abnormal (Charging System)",
        "description": "Tegangan sistem kelistrikan motor terlalu tinggi (>16V) atau terlalu rendah (<10V).",
        "symptoms": "Lampu utama redup/putus, aki tekor terus atau aki mendidih.",
        "probable_cause": "Kiprok (Regulator/Rectifier) rusak, spull pengisian gosong, atau aki soak.",
    },
    50: {
        "name": "ECU Internal Memory Fault",
        "description": "Kerusakan sirkuit mikroprosesor atau ROM internal pada ECU.",
        "symptoms": "Mesin tidak dapat dihidupkan, motor mati total.",
        "probable_cause": "ECU terkena lonjakan voltase petir/korsleting parah atau kemasukan air.",
    },
}


def lookup_dtc(code: int, is_active: bool = True) -> DTCFault:
    """Helper to get a full DTCFault object by numeric fault code."""
    data = YAMAHA_MIO_GT_DTC_MAP.get(code)
    if data:
        return DTCFault(
            code=code,
            name=data["name"],
            description=data["description"],
            symptoms=data["symptoms"],
            probable_cause=data["probable_cause"],
            is_active=is_active,
        )
    return DTCFault(
        code=code,
        name=f"Yamaha Unknown Code {code}",
        description="Kode kerusakan tidak terdaftar dalam database standar Mio GT.",
        symptoms="Periksa buku pedoman reparasi resmi Yamaha (Service Manual).",
        probable_cause="Sensor/aktuator tidak dikenal atau kode ECU model baru.",
        is_active=is_active,
    )
