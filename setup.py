"""
Setup configuration for Yamaha ECU Diagnostic, RPS & Mapping Software Package.
Enables pip installation: pip install -e .
Provides CLI commands: yamaha-ecu, yamaha-ecu-studio
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="yamaha-ecu-toolkit",
    version="1.1.0",
    author="Adrian Vallenz",
    description="Full ECU Diagnostic, Real-Time RPS Telemetry & Tuning Software Suite for Yamaha Motorcycle (Mio GT 2015 115cc YMJET-FI)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AdrianVallenz/YAMAHA-ECU-SCANNER-MIO-GT",
    packages=find_packages(),
    package_data={
        "yamaha_ecu": [
            "web/static/*",
            "firmware/*",
            "presets/*",
        ],
    },
    include_package_data=True,
    install_requires=[
        "pyserial>=3.5",
        "matplotlib>=3.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "yamaha-ecu=yamaha_ecu.cli:main",
            "yamaha-ecu-app=yamaha_ecu.app:main",
            "yamaha-ecu-studio=visual_dashboard:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Topic :: System :: Hardware :: Hardware Drivers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.14",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
)
