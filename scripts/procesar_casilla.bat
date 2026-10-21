@echo off
REM Programador de tareas de Windows: cada 5 minutos, de lunes a viernes.
cd /d "%~dp0.."
python scripts\procesar_casilla.py >> datos\casilla.log 2>&1
