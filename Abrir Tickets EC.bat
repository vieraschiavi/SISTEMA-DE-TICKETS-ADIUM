@echo off
REM Abre la mesa de tickets en el navegador.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python -m streamlit run app\app.py
