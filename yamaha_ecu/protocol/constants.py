"""
Yamaha Diagnostic & Communication Protocol Constants.
Optimized for Yamaha Mio GT 2015 (54P / 2BJ Engine Control Unit).
"""

# Protocol Frame Headers
YDIS_REQUEST_HEADER = 0x12       # Client -> ECU
YDIS_RESPONSE_HEADER = 0x80      # ECU -> Client
YDIS_NEGATIVE_RESPONSE = 0x7F    # Negative Response Code (NRC)

# Standard Commands / Service Identifiers
YDIS_CMD_INIT = 0x81             # Start Diagnostic Session / Wakeup
YDIS_CMD_READ_LIVE_DATA = 0x21   # Real-time Parameter Streaming (RPS / RPM)
YDIS_CMD_READ_DTC = 0x13         # Read Diagnostic Trouble Codes
YDIS_CMD_CLEAR_DTC = 0x14        # Clear Diagnostic Trouble Codes
YDIS_CMD_READ_DIAG_ITEM = 0x22   # Read DIAG sensor test code (d01 - d70)
YDIS_CMD_ACTUATOR_TEST = 0x30    # Actuator Output Test (Ignition spark, injector click)
YDIS_CMD_READ_MAP_CALIBRATION = 0x23 # Read ECU Calibration / Limits / CO trim
YDIS_CMD_SET_CO_TRIM = 0x24      # Adjust CO Trim (-30 to +30)
YDIS_CMD_READ_MEMORY_BY_ADDR = 0x25  # Read Flash/EEPROM memory block (if supported)

# Default Baud Rates
BAUDRATE_YAMAHA_DEFAULT = 10400
BAUDRATE_YAMAHA_FALLBACK = 9600

# DIAG Mode Item Mappings for Mio GT
DIAG_ITEMS = {
    1: {"name": "d01: Throttle Position Sensor Angle", "unit": "deg / raw", "min": 15, "max": 100},
    3: {"name": "d03: Intake Air Pressure (MAP)", "unit": "kPa", "min": 10, "max": 110},
    5: {"name": "d05: Intake Air Temperature (IAT)", "unit": "°C", "min": -20, "max": 100},
    7: {"name": "d07: Vehicle Speed Pulse", "unit": "pulses", "min": 0, "max": 999},
    8: {"name": "d08: Lean Angle Sensor Voltage", "unit": "x0.1 V", "min": 10, "max": 45},
    9: {"name": "d09: Battery Voltage", "unit": "x0.1 V", "min": 90, "max": 150},
    30: {"name": "d30: Ignition Spark Actuator Test", "unit": "clicks (5x)", "min": 0, "max": 1},
    36: {"name": "d36: Fuel Injector Actuator Test", "unit": "clicks (5x)", "min": 0, "max": 1},
    50: {"name": "d50: Fuel Injection System Relay Test", "unit": "state", "min": 0, "max": 1},
    52: {"name": "d52: Idle Speed Control (ISC) Step Test", "unit": "steps", "min": 0, "max": 120},
    60: {"name": "d60: EEPROM Self-Diagnostic Code", "unit": "00:OK, 01:ERR", "min": 0, "max": 1},
    61: {"name": "d61: Malfunction History Code", "unit": "DTC code", "min": 0, "max": 99},
    62: {"name": "d62: Malfunction History Erasure", "unit": "00:Cleared", "min": 0, "max": 1},
    70: {"name": "d70: Control Number / ECU ROM Version", "unit": "num", "min": 0, "max": 255},
}
