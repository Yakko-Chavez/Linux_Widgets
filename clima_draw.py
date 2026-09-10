"""Dibujo vectorial Clima Dorado con Cairo.

100% procedural, sin imagenes externas. Estilo cuero negro + filetes
dorados a juego con la Agenda de Lujo (vertical).
Funcion: draw_clima(cr, w, h, data, locked=False)
  data = {"city": "Puebla", "temp": 17.2, "code": 3, "apparent": 17.6,
          "hum": 78, "wind": 4.3,
          "days": [{"dow": "JUE", "code": 51, "max": 25.0, "min": 12.3}...],
          "updated": "20:15", "offline": False}
"""

import math

GOLD = (0.79, 0.64, 0.15)
GOLD_LIGHT = (0.93, 0.82, 0.45)
GOLD_DARK = (0.48, 0.37, 0.10)
CREAM = (0.92, 0.89, 0.80)
MUTED = (0.55, 0.52, 0.45)


def _rr(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _text_centered(cr, cx, y, text, size, color, serif=True, bold=True):
    cr.save()
    cr.select_font_face("Serif" if serif else "Sans", 0, 1 if bold else 0)
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(cx - ext.width / 2 - ext.x_bearing, y)
    cr.show_text(text)
    cr.restore()


def wmo_label(code):
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "—"
    if c == 0:
        return "Despejado"
    if c in (1, 2):
        return "Poco nuboso"
    if c == 3:
        return "Nublado"
    if c in (45, 48):
        return "Niebla"
    if c in (51, 53, 55, 56, 57):
        return "Llovizna"
    if c in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Lluvia"
    if c in (71, 73, 75, 77, 85, 86):
        return "Nieve"
    if c in (95, 96, 99):
        return "Tormenta"
    return "Nublado"


def _draw_sun(cr, cx, cy, r):
    cr.save()
    cr.new_sub_path()
    cr.arc(cx, cy, r * 0.45, 0, 2 * math.pi)
    cr.set_source_rgb(*GOLD_LIGHT)
    cr.fill()
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(max(1.5, r * 0.07))
    for i in range(8):
        a = i * math.pi / 4
        cr.move_to(cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.62)
        cr.line_to(cx + math.cos(a) * r * 0.95, cy + math.sin(a) * r * 0.95)
        cr.stroke()
    cr.restore()


def _draw_cloud(cr, cx, cy, r, color=CREAM, xoff=0.0):
    cr.save()
    cr.set_source_rgb(*color)
    for dx, dy, rr in [(-0.35, 0.15, 0.38), (0.0, -0.05, 0.5), (0.38, 0.15, 0.34)]:
        cr.new_sub_path()
        cr.arc(cx + (dx + xoff) * r, cy + dy * r, rr * r, 0, 2 * math.pi)
        cr.fill()
    cr.restore()


def _draw_icon(cr, cx, cy, r, code):
    """Icono Cairo segun codigo WMO."""
    try:
        c = int(code)
    except (TypeError, ValueError):
        c = 3
    if c == 0:
        _draw_sun(cr, cx, cy, r)
    elif c in (1, 2):
        _draw_sun(cr, cx - r * 0.25, cy - r * 0.2, r * 0.7)
        _draw_cloud(cr, cx + r * 0.15, cy + r * 0.25, r * 0.8)
    elif c in (45, 48):
        _draw_cloud(cr, cx, cy - r * 0.15, r * 0.9, MUTED)
        cr.save()
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.set_line_width(max(1.2, r * 0.07))
        for i, yy in enumerate((-0.05, 0.2, 0.45)):
            x0 = cx - r * (0.5 - i * 0.08)
            cr.move_to(x0, cy + yy * r)
            cr.line_to(x0 + r * 0.9, cy + yy * r)
            cr.stroke()
        cr.restore()
    elif c in (71, 73, 75, 77, 85, 86):
        _draw_cloud(cr, cx, cy - r * 0.2, r * 0.9)
        cr.save()
        cr.set_source_rgb(*CREAM)
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(r * 0.4)
        for i, dx in enumerate((-0.4, 0.0, 0.4)):
            cr.move_to(cx + dx * r - r * 0.1, cy + r * 0.55)
            cr.show_text("*")
        cr.restore()
    elif c in (95, 96, 99):
        _draw_cloud(cr, cx, cy - r * 0.25, r * 0.9, (0.55, 0.55, 0.58))
        cr.save()
        cr.move_to(cx + r * 0.1, cy)
        cr.line_to(cx - r * 0.15, cy + r * 0.45)
        cr.line_to(cx + r * 0.05, cy + r * 0.45)
        cr.line_to(cx - r * 0.15, cy + r * 0.9)
        cr.close_path()
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.fill()
        cr.restore()
    else:  # nublado / llovizna / lluvia
        _draw_cloud(cr, cx, cy - r * 0.2, r * 0.9)
        rainy = c in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82)
        if rainy:
            cr.save()
            cr.set_source_rgb(0.55, 0.70, 0.95)
            cr.set_line_width(max(1.5, r * 0.09))
            cr.set_line_cap(1)
            for dx in (-0.35, 0.0, 0.35):
                cr.move_to(cx + dx * r, cy + r * 0.35)
                cr.line_to(cx + (dx - 0.12) * r, cy + r * 0.7)
                cr.stroke()
            cr.restore()


def draw_clima(cr, w, h, data, locked=False):
    import cairo
    data = data or {}
    city = str(data.get("city", "PUEBLA")).upper()
    temp = data.get("temp")
    code = data.get("code", 3)
    apparent = data.get("apparent")
    hum = data.get("hum")
    wind = data.get("wind")
    days = data.get("days", [])[:5]
    updated = data.get("updated", "")
    offline = bool(data.get("offline", False))

    pad = 6
    cr.save()
    _rr(cr, pad, pad, w - pad * 2, h - pad * 2, 18)
    g = cairo.RadialGradient(w / 2, h * 0.2, 10, w / 2, h / 2, h * 0.7)
    g.add_color_stop_rgb(0, 0.09, 0.09, 0.10)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.025)
    cr.set_source(g)
    cr.fill()
    _rr(cr, pad, pad, w - pad * 2, h - pad * 2, 18)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(2.2)
    cr.stroke()
    _rr(cr, pad + 6, pad + 6, w - (pad + 6) * 2, h - (pad + 6) * 2, 14)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1.1)
    cr.stroke()
    for rx, ry in [(pad + 9, pad + 9), (w - pad - 9, pad + 9),
                   (pad + 9, h - pad - 9), (w - pad - 9, h - pad - 9)]:
        cr.new_sub_path()
        cr.arc(rx, ry, 3.4, 0, 2 * math.pi)
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.fill()
    cr.restore()

    # header ciudad
    _text_centered(cr, w / 2, 40, city, 22, GOLD_LIGHT)
    cr.save()
    cr.move_to(28, 52)
    cr.line_to(w - 28, 52)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1)
    cr.stroke()
    cr.restore()

    # icono + temp actual
    _draw_icon(cr, w / 2, 118, 44, code)
    ttxt = f"{temp:.0f}°" if isinstance(temp, (int, float)) else "--°"
    _text_centered(cr, w / 2, 200, ttxt, 64, GOLD_LIGHT, serif=False)
    _text_centered(cr, w / 2, 224, wmo_label(code), 15, CREAM, serif=False)

    # detalles
    det = []
    if isinstance(apparent, (int, float)):
        det.append(f"Sens {apparent:.0f}°")
    if isinstance(hum, (int, float)):
        det.append(f"Hum {hum:.0f}%")
    if isinstance(wind, (int, float)):
        det.append(f"Vie {wind:.0f} km/h")
    if det:
        _text_centered(cr, w / 2, 248, " · ".join(det), 12.5, MUTED,
                       serif=False, bold=False)

    # separador
    cr.save()
    cr.move_to(28, 262)
    cr.line_to(w - 28, 262)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1)
    cr.stroke()
    cr.restore()

    # tira 5 dias (anclada abajo para no dejar hueco)
    n = max(1, len(days))
    col_w = (w - 48) / 5
    base_y = h - 198
    for i, d in enumerate(days):
        cx = 24 + col_w * (i + 0.5)
        _text_centered(cr, cx, base_y, str(d.get("dow", "")), 12,
                       GOLD_LIGHT, serif=False)
        _draw_icon(cr, cx, base_y + 30, 20, d.get("code", 3))
        mx, mn = d.get("max"), d.get("min")
        mtxt = f"{mx:.0f}°/{mn:.0f}°" if isinstance(mx, (int, float)) and isinstance(mn, (int, float)) else "--"
        _text_centered(cr, cx, base_y + 66, mtxt, 12.5, CREAM, serif=False)
        if i < n - 1:
            cr.save()
            cr.move_to(24 + col_w * (i + 1), base_y - 6)
            cr.line_to(24 + col_w * (i + 1), base_y + 60)
            cr.set_source_rgba(0.48, 0.37, 0.10, 0.5)
            cr.set_line_width(1)
            cr.stroke()
            cr.restore()

    foot = f"Act. {updated}" if updated else ""
    if offline:
        foot = (foot + " · sin conexión").strip(" ·")
    if foot:
        _text_centered(cr, w / 2, h - 16, foot, 10.5, MUTED,
                       serif=False, bold=False)
    if locked:
        cr.save()
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(14)
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.move_to(w - 30, h - 14)
        cr.show_text("🔒")
        cr.restore()
