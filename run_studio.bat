@echo off
title Yamaha ECU Diagnostic & Telemetry Studio - Mio GT 2015
echo ======================================================================
echo    YAMAHA MOTORCYCLE ECU DIAGNOSTIC, TELEMETRY & TUNING STUDIO
echo    Target: Yamaha Mio GT 115cc YMJET-FI (ECU 54P-H591A-00)
echo ======================================================================
echo.
echo Memulai server studio dan membuka browser...
python visual_dashboard.py %*
pause
