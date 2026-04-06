@echo off
:: Wechselt in das Verzeichnis, in dem das Skript liegt
cd /d "C:\Users\marti\OneDrive\Keyboard\GigPerformer\Scripts"

title GP Geisterhand Server
echo ==========================================
echo STARTE GIG PERFORMER GEISTERHAND...
echo ==========================================

:: Startet das Python-Skript
python SwitchGPToGlobal.py

:: Falls das Skript abstürzt, bleibt das Fenster für die Fehlersuche offen
echo.
echo [WARNUNG] Das Skript wurde beendet.
pause