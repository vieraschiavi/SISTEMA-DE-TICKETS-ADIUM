"""
Quién está usando la app: el ingreso con la cuenta de Microsoft de Adium y
lo que cada rol puede hacer.

**La app no ve nunca una contraseña.** «Ingresar» abre la página de inicio
de sesión de Microsoft en el navegador (la misma de Outlook y Teams, con el
MFA de Adium); Microsoft le devuelve a la app un token de esa persona, que
vive en memoria mientras la app está abierta. Cerrar la app es cerrar la
sesión. Lo hace MSAL, la biblioteca oficial de Microsoft (`pip install msal`).

Lo que se le pide a Microsoft (permisos delegados: la persona sólo puede lo
que su cuenta ya puede):

* `Sites.ReadWrite.All` — leer y escribir las listas del sitio de la mesa.
* `Mail.ReadWrite.Shared` — leer la casilla compartida y marcar lo leído.
* `Mail.Send.Shared` — mandar como la casilla (acuses, avisos, encuestas).

Los roles salen de la lista Personas (la carga un coordinador): analista y
coordinador trabajan la mesa; cualquier otra cuenta de Adium no entra acá
(escribe a la casilla). Sin Streamlit: se prueba sola.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import catalogos as C

ALCANCES = ("Sites.ReadWrite.All", "Mail.ReadWrite.Shared", "Mail.Send.Shared")

COORDINADOR, ANALISTA = "coordinador", "analista"
EQUIPO = (ANALISTA, COORDINADOR)


class ErrorAcceso(ValueError):
    """No se pudo entrar, con el motivo en castellano."""


@dataclass(frozen=True)
class Identidad:
    mail: str
    nombre: str
    tenant: str = ""


def identidad(claims: dict, cfg) -> Identidad:
    """La persona del token. Se rechaza una cuenta de otro tenant o de un
    dominio que no es de Adium: el registro de la app debería impedirlo,
    pero acá se vuelve a mirar."""
    mail = (claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "").strip().lower()
    if "@" not in mail:
        raise ErrorAcceso("Microsoft no devolvió el correo de la cuenta.")
    tenant = claims.get("tid", "")
    if cfg.entra_tenant and tenant and tenant.lower() != cfg.entra_tenant.lower():
        raise ErrorAcceso(f"{mail} es de otra organización: entrá con tu cuenta de Adium.")
    dominio = mail.split("@", 1)[1]
    if cfg.dominios and dominio not in cfg.dominios:
        raise ErrorAcceso(f"{mail} no es una cuenta de Adium ({', '.join(cfg.dominios[:3])}…).")
    return Identidad(mail, claims.get("name") or mail.split("@")[0], tenant)


class Sesion:
    """La sesión de UNA persona en ESTA PC.

    `app` es inyectable para los tests: cualquier objeto con la interfaz de
    `msal.PublicClientApplication` (`acquire_token_interactive`,
    `acquire_token_silent`, `get_accounts`, `remove_account`)."""

    def __init__(self, cfg, app=None):
        faltan = cfg.faltantes_compartida()
        if faltan:
            raise ErrorAcceso("Para entrar con la cuenta de Adium falta configurar: " + ", ".join(faltan)
                              + " (en config.equipo.toml, ver docs/EQUIPO.md).")
        if app is None:
            try:
                import msal
            except ImportError as e:
                raise ErrorAcceso("Falta la biblioteca de Microsoft para el ingreso: pip install msal "
                                  "(el «Abrir Tickets EC.bat» la instala).") from e
            try:      # MSAL ya consulta a Microsoft acá: sin red o con un tenant mal escrito, falla
                app = msal.PublicClientApplication(
                    cfg.entra_cliente, authority=f"https://login.microsoftonline.com/{cfg.entra_tenant}")
            except Exception as e:   # noqa: BLE001 — requests/ValueError de MSAL, con el motivo
                raise ErrorAcceso(f"No se pudo contactar a Microsoft con el tenant «{cfg.entra_tenant}» "
                                  f"(¿hay red? ¿está bien entra_tenant en config.equipo.toml?): {e}") from e
        self.cfg, self.app = cfg, app
        self.quien: Identidad | None = None

    def ingresar(self) -> Identidad:
        """Abre el inicio de sesión de Microsoft en el navegador y espera."""
        dominio = self.cfg.dominios[0] if self.cfg.dominios else None
        try:
            r = self.app.acquire_token_interactive(list(ALCANCES), prompt="select_account", domain_hint=dominio,
                                                   timeout=300)
        except Exception as e:   # noqa: BLE001 — sin navegador, sin red: se dice, no se cae la app
            raise ErrorAcceso(f"No se pudo abrir el inicio de sesión de Microsoft: {e}") from e
        if "access_token" not in r:
            raise ErrorAcceso("No se completó el ingreso: " + (r.get("error_description") or r.get("error")
                                                               or "se cerró la ventana de Microsoft") + ".")
        self.quien = identidad(r.get("id_token_claims") or {}, self.cfg)
        return self.quien

    def token(self) -> str:
        """El token vigente (MSAL lo renueva solo mientras la sesión dura)."""
        # La cuenta de esta persona, sin depender de cómo escribió las mayúsculas.
        cuentas = [c for c in self.app.get_accounts()
                   if self.quien and (c.get("username") or "").lower() == self.quien.mail]
        r = self.app.acquire_token_silent(list(ALCANCES), account=cuentas[0]) if cuentas else None
        if not r or "access_token" not in r:
            raise ErrorAcceso("La sesión venció: volvé a ingresar con tu cuenta de Adium.")
        return r["access_token"]

    def salir(self) -> None:
        for cuenta in self.app.get_accounts():
            self.app.remove_account(cuenta)
        self.quien = None


# ==========================================================================
# Qué puede cada uno
# ==========================================================================
def rol(db, mail: str) -> str:
    """«coordinador», «analista» o «» (no es del equipo, o está dado de baja)."""
    p = db.persona(mail) if mail else None
    return p["rol"] if p and p["activo"] and p["rol"] in EQUIPO else ""


def puede_actuar(su_rol: str, mail: str, t: dict) -> bool:
    """Tomar, resolver, pedir información, cancelar y editar los datos. El
    coordinador, siempre; el analista, en los suyos y en los sin asignar.
    (Lo que de verdad impide escribir es el permiso del sitio: esto ordena
    el trabajo, no reemplaza a SharePoint.)"""
    if su_rol == COORDINADOR:
        return True
    return su_rol == ANALISTA and t["estado"] not in C.FINALES and t["analista_mail"] in (None, "", mail)


def puede_asignar(su_rol: str) -> bool:
    """Asignarle un ticket a OTRO integrante (tomarlo uno mismo lo puede cualquiera del equipo)."""
    return su_rol == COORDINADOR


def puede_configurar(su_rol: str) -> bool:
    """Dar de alta o de baja integrantes."""
    return su_rol == COORDINADOR
