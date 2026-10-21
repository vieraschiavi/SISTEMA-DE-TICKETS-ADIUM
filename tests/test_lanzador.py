"""«Abrir Tickets EC.bat», revisado sin Windows: las trampas de cmd.exe que
ya rompieron el .bat de la suite, y que ante un error la ventana NO se cierra
sin decir por qué (el primer .bat de la mesa abría y se cerraba)."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BAT = RAIZ / "Abrir Tickets EC.bat"


def _texto() -> str:
    return BAT.read_bytes().decode("ascii")


def _bloques(texto):
    """Cada línea con la profundidad de bloque `( … )` en la que está."""
    nivel = 0
    for cruda in texto.splitlines():
        sin = re.sub(r'"[^"]*"', '""', cruda).replace("^(", "").replace("^)", "")
        yield cruda, nivel
        if cruda.strip().lower().startswith(("rem", "::", "echo")):
            continue
        nivel += sin.count("(") - sin.count(")")


def test_ascii_y_finales_de_linea_de_windows():
    crudo = BAT.read_bytes()
    crudo.decode("ascii")                                   # sin acentos: cmd.exe los muestra rotos
    assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b"")


def test_los_bloques_cierran():
    *_, (ultima, nivel) = list(_bloques(_texto()))
    assert sum(1 for _ in _bloques(_texto())) and nivel == 0


def test_adentro_de_un_bloque_ni_dp0_ni_rem_con_parentesis_ni_parentesis_sin_escapar():
    for linea, nivel in _bloques(_texto()):
        if nivel <= 0:
            continue
        assert "%~dp0" not in linea, f"%~dp0 adentro de un bloque: {linea}"
        s = linea.strip().lower()
        if s.startswith("rem"):
            assert not re.search(r'[()"]', linea), f"REM con comillas o paréntesis adentro de un bloque: {linea}"
        if s.startswith("echo"):
            resto = linea.replace("^(", "").replace("^)", "")
            assert "(" not in resto and ")" not in resto, f"echo con paréntesis sin escapar en un bloque: {linea}"


def test_cada_salida_con_error_espera_antes_de_cerrar():
    lineas = _texto().splitlines()
    for i, linea in enumerate(lineas):
        if linea.strip().lower() == "exit /b 1":
            previas = [x.strip().lower() for x in lineas[max(0, i - 3):i]]
            assert "pause" in previas, f"exit /b 1 sin pause antes (línea {i + 1}): la ventana se cierra sola"


def test_consigue_python_instala_lo_de_la_app_y_abre():
    t = _texto()
    assert "packaging\\conseguir_python.ps1" in t and (RAIZ / "packaging" / "conseguir_python.ps1").is_file()
    assert "requirements-app.txt" in t and (RAIZ / "requirements-app.txt").is_file()
    assert "--no-index" in t and "ruedas" in t, "falta el camino sin salida a PyPI"
    assert "(1, 50)" in t, "no verifica la versión de Streamlit"
    assert "-m streamlit run" in t
    assert "streamlit>=1.50" in (RAIZ / "requirements-app.txt").read_text()


def test_si_la_app_termina_con_error_la_ventana_queda_abierta():
    t = _texto()
    despues = t[t.index("-m streamlit run"):]
    assert "if errorlevel 1" in despues and "pause" in despues

