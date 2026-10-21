@echo off
REM Programador de tareas de Windows: todos los dias a las 06:30, antes del refresco de Power BI.
cd /d "%~dp0.."
python scripts\exportar_powerbi.py %* >> datos\exportar.log 2>&1
