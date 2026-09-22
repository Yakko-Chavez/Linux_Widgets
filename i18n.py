"""ES/EN para los widgets de escritorio.

Sin gettext (ni msgfmt ni binarios .mo): las claves son el texto en ingles
y el diccionario "es" mapea al espanol. En cualquier otro idioma se muestra
la clave tal cual (ingles), asi el fallback no requiere diccionario propio.

Deteccion: LANGUAGE > LC_ALL > LC_MESSAGES > LANG; un codigo que empiece por
"es" elige espanol y por "en" (o nada) elige ingles. Los procesos lanzados
por la extension heredan el entorno de la sesion GNOME, por lo que siguen el
idioma configurado en Configuracion > Region e idioma.
"""

import os

_ES = {
    # ---- menus comunes ----
    "Lock clicks": "Bloquear clicks",
    "Lock clicks ✓": "Bloquear clicks ✓",
    "Size +": "Tamaño +",
    "Size −": "Tamaño −",
    "Settings…": "Configuración…",
    "Quit": "Salir",
    # ---- dialogo de configuracion ----
    "Settings": "Configuración",
    "Apply": "Aplicar",
    "Cancel": "Cancelar",
    "Size": "Tamaño",
    "Height": "Alto",
    "Opacity": "Opacidad",
    "Smooth sweep": "Sweep suave",
    "Week starts Monday": "La semana empieza en lunes",
    "City": "Ciudad",
    "Latitude": "Latitud",
    "Longitude": "Longitud",
    # ---- clima ----
    "Refresh now": "Actualizar ahora",
    "Clear": "Despejado",
    "Partly cloudy": "Poco nuboso",
    "Overcast": "Nublado",
    "Fog": "Niebla",
    "Drizzle": "Llovizna",
    "Rain": "Lluvia",
    "Snow": "Nieve",
    "Storm": "Tormenta",
    "offline": "sin conexión",
    "Upd. {t}": "Act. {t}",
    "MON": "LUN",
    "TUE": "MAR",
    "WED": "MIÉ",
    "THU": "JUE",
    "FRI": "VIE",
    "SAT": "SÁB",
    "SUN": "DOM",
    # ---- agenda ----
    "Previous month": "Mes anterior",
    "Next month": "Mes siguiente",
    "Go to today": "Ir a hoy",
    "JANUARY": "ENERO",
    "FEBRUARY": "FEBRERO",
    "MARCH": "MARZO",
    "APRIL": "ABRIL",
    "MAY": "MAYO",
    "JUNE": "JUNIO",
    "JULY": "JULIO",
    "AUGUST": "AGOSTO",
    "SEPTEMBER": "SEPTIEMBRE",
    "OCTOBER": "OCTUBRE",
    "NOVEMBER": "NOVIEMBRE",
    "DECEMBER": "DICIEMBRE",
    "monday": "lunes",
    "tuesday": "martes",
    "wednesday": "miércoles",
    "thursday": "jueves",
    "friday": "viernes",
    "saturday": "sábado",
    "sunday": "domingo",
    "Today · {wd} {d} of {mon}": "Hoy · {wd} {d} de {mon}",
    "Week Letters MonFirst": "L M M J V S D",
    "Week Letters SunFirst": "D L M M J V S",
    # ---- sysmon ----
    "DISK": "DISCO",
    "NET": "RED",
}


def _detect():
    env = ""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if val:
            env = val
            break
    for code in env.replace(":", " ").replace(";", " ").split():
        c = code.split(".")[0].lower()
        if c.startswith("es"):
            return "es"
        if c.startswith("en"):
            return "en"
    return "en"


_LANG = _detect()


def lang():
    """Idioma activo: 'es' o 'en'."""
    return _LANG


def _(key, **fmt):
    """Traduce la clave (texto ingles) al idioma activo.

    Con **fmt aplica str.format: _("Today · {wd} {d} of {mon}", wd=..., ...).
    """
    text = _ES.get(key, key) if _LANG == "es" else key
    if fmt:
        text = text.format(**fmt)
    return text
