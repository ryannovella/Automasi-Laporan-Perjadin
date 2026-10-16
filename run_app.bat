@echo off
title Automasi Laporan Perjadin - Pamsimas
echo ========================================================
echo   Menjalankan Aplikasi Automasi Laporan Perjadin (Streamlit)
echo   Balai Prasarana Permukiman Wilayah (BPPW) Jawa Tengah
echo   Kementerian Pekerjaan Umum (Kementerian PU)
echo ========================================================
echo.
cd /d "%~dp0"
python -m streamlit run app.py
pause
