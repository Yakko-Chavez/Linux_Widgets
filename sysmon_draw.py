"""Dibujo vectorial Monitor Dorado con Cairo.

100% procedural, sin imagenes externas. Estilo cuero negro + filetes
dorados a juego con la Agenda de Lujo.
Funcion: draw_sysmon(cr, w, h, data, locked=False)
  data = {"dials": [{"label": "CPU", "pct": 0-100, "main": "27%",
                     "sub": "55C · 16 hilos"}...],
          "minis": [{"label": "EFI", "pct": 1, "text": "6M/1.1G"},
                    {"label": "SWAP", "pct": 0, "text": "1M/4G"}],
          "title": "MONITOR"}
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


def _gold_stroke(cr):
    g = cr  # placeholder para mantener firma simple
    return GOLD


def _draw_dial(cr, cx, cy, r, label, pct, main, sub):
    import cairo
    pct = max(0.0, min(100.0, float(pct or 0)))

    # aro exterior dorado
    cr.save()
    cr.new_sub_path()
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    g = cairo.RadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.2, cx, cy, r)
    g.add_color_stop_rgb(0, *GOLD_LIGHT)
    g.add_color_stop_rgb(0.6, *GOLD)
    g.add_color_stop_rgb(1, *GOLD_DARK)
    cr.set_source(g)
    cr.set_line_width(max(2.0, r * 0.09))
    cr.stroke()
    # fondo interior negro
    cr.new_sub_path()
    cr.arc(cx, cy, r * 0.92, 0, 2 * math.pi)
    g2 = cairo.RadialGradient(cx, cy - r * 0.3, r * 0.1, cx, cy, r)
    g2.add_color_stop_rgb(0, 0.10, 0.10, 0.11)
    g2.add_color_stop_rgb(1, 0.03, 0.03, 0.035)
    cr.set_source(g2)
    cr.fill()
    cr.restore()

    # ticks 270 grados: de 135 a 405 (en rad: 0.75pi -> 2.25pi)
    a0 = math.pi * 0.75
    a1 = math.pi * 2.25
    cr.save()
    for i in range(27):
        a = a0 + (a1 - a0) * i / 26.0
        big = (i % 3 == 0)
        r1 = r * 0.86
        r2 = r * (0.74 if big else 0.79)
        cr.new_sub_path()
        cr.arc(cx, cy, r1, 0, 0)  # mover sin linea fantasma
        x1 = cx + math.cos(a) * r1
        y1 = cy + math.sin(a) * r1
        x2 = cx + math.cos(a) * r2
        y2 = cy + math.sin(a) * r2
        cr.move_to(x1, y1)
        cr.line_to(x2, y2)
        cr.set_source_rgb(*(CREAM if big else MUTED))
        cr.set_line_width(r * 0.028 if big else r * 0.014)
        cr.set_line_cap(1)
        cr.stroke()
    cr.restore()

    # arco de valor dorado
    cr.save()
    frac = pct / 100.0
    cr.new_sub_path()
    cr.arc(cx, cy, r * 0.66, a0, a0 + (a1 - a0) * frac)
    grad = cairo.LinearGradient(cx - r, cy - r, cx + r, cy + r)
    grad.add_color_stop_rgb(0, *GOLD_DARK)
    grad.add_color_stop_rgb(0.5, *GOLD)
    grad.add_color_stop_rgb(1, *GOLD_LIGHT)
    cr.set_source(grad)
    cr.set_line_width(r * 0.12)
    cr.set_line_cap(1)
    cr.stroke()
    # aguja
    a = a0 + (a1 - a0) * frac
    cr.move_to(cx - math.cos(a) * r * 0.12, cy - math.sin(a) * r * 0.12)
    cr.line_to(cx + math.cos(a) * r * 0.58, cy + math.sin(a) * r * 0.58)
    cr.set_source_rgb(*CREAM)
    cr.set_line_width(max(1.5, r * 0.035))
    cr.stroke()
    cr.restore()

    # eje
    cr.save()
    cr.new_sub_path()
    cr.arc(cx, cy, r * 0.07, 0, 2 * math.pi)
    cr.set_source_rgb(*GOLD_LIGHT)
    cr.fill()
    cr.new_sub_path()
    cr.arc(cx, cy, r * 0.035, 0, 2 * math.pi)
    cr.set_source_rgb(0.05, 0.05, 0.05)
    cr.fill()
    cr.restore()

    _text_centered(cr, cx, cy - r * 1.12, label, r * 0.24, GOLD_LIGHT)
    # porcentaje debajo del dial (fuera), en dorado
    _text_centered(cr, cx, cy + r * 1.38, main, r * 0.30, GOLD_LIGHT, serif=False)
    if sub:
        _text_centered(cr, cx, cy + r * 1.62, sub, r * 0.155, MUTED, serif=False, bold=False)


def _draw_mini(cr, x, y, w, label, pct, text):
    import cairo
    pct = max(0.0, min(100.0, float(pct or 0)))
    cr.save()
    _text_centered(cr, x + 24, y + 11, label, 11, GOLD_LIGHT, serif=False)
    bx, bw, bh = x + 52, w - 52, 10
    by = y + 3
    _rr(cr, bx, by, bw, bh, 5)
    cr.set_source_rgb(0.08, 0.08, 0.09)
    cr.fill()
    if pct > 0.5:
        _rr(cr, bx + 1, by + 1, (bw - 2) * pct / 100.0, bh - 2, 4)
        g = cairo.LinearGradient(bx, 0, bx + bw, 0)
        g.add_color_stop_rgb(0, *GOLD_DARK)
        g.add_color_stop_rgb(1, *GOLD_LIGHT)
        cr.set_source(g)
        cr.fill()
    _rr(cr, bx, by, bw, bh, 5)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1)
    cr.stroke()
    cr.set_source_rgb(*MUTED)
    cr.select_font_face("Sans", 0, 0)
    cr.set_font_size(10.5)
    cr.move_to(bx, y + 25)
    cr.show_text(text)
    cr.restore()


def sysmon_layout(w, h):
    """Geometria de diales para el widget (coords logicas)."""
    header_h = 58
    footer_h = 58
    area_h = h - header_h - footer_h
    # 5 diales en horizontal, compactos (textos debajo del dial)
    cy = header_h + area_h * 0.36
    xs = [w * (0.11 + 0.195 * i) for i in range(5)]
    r = min(w * 0.082, area_h * 0.27)
    return {
        "title_y": 32,
        "dials_xy": [(x, cy) for x in xs],
        "dial_r": r,
        "mini_y": h - footer_h + 8,
        "footer_y": h - 12,
    }


def draw_sysmon(cr, w, h, data, locked=False):
    import cairo
    title = (data or {}).get("title", "MONITOR")
    dials = (data or {}).get("dials", [])
    minis = (data or {}).get("minis", [])
    foot = (data or {}).get("footer", "")

    pad = 6
    # fondo cuero negro
    cr.save()
    _rr(cr, pad, pad, w - pad * 2, h - pad * 2, 18)
    g = cairo.RadialGradient(w / 2, h * 0.25, 10, w / 2, h / 2, h * 0.7)
    g.add_color_stop_rgb(0, 0.09, 0.09, 0.10)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.025)
    cr.set_source(g)
    cr.fill()
    # filete dorado doble
    _rr(cr, pad, pad, w - pad * 2, h - pad * 2, 18)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(2.2)
    cr.stroke()
    _rr(cr, pad + 6, pad + 6, w - (pad + 6) * 2, h - (pad + 6) * 2, 14)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1.1)
    cr.stroke()
    # remaches
    for rx, ry in [(pad + 9, pad + 9), (w - pad - 9, pad + 9),
                   (pad + 9, h - pad - 9), (w - pad - 9, h - pad - 9)]:
        cr.new_sub_path()
        cr.arc(rx, ry, 3.4, 0, 2 * math.pi)
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.fill()
    cr.restore()

    lay = sysmon_layout(w, h)
    _text_centered(cr, w / 2, lay["title_y"], title, 21, GOLD_LIGHT)
    # linea bajo titulo
    cr.save()
    cr.move_to(28, lay["title_y"] + 12)
    cr.line_to(w - 28, lay["title_y"] + 12)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1)
    cr.stroke()
    cr.restore()

    r = lay["dial_r"]
    for i, pos in enumerate(lay["dials_xy"]):
        if i < len(dials):
            d = dials[i]
            _draw_dial(cr, pos[0], pos[1], r, d.get("label", ""),
                       d.get("pct", 0), d.get("main", ""),
                       d.get("sub", ""))

    # minis EFI / SWAP
    my = lay["mini_y"]
    mw = (w - 48) / 2 - 6
    for i, m in enumerate(minis[:2]):
        _draw_mini(cr, 24 + i * (mw + 12), my, mw,
                   m.get("label", ""), m.get("pct", 0), m.get("text", ""))

    if foot:
        _text_centered(cr, w / 2, lay["footer_y"], foot, 10.5, MUTED,
                       serif=False, bold=False)
    if locked:
        # candadito dorado abajo-derecha (igual que la agenda)
        cr.save()
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(14)
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.move_to(w - 30, h - 14)
        cr.show_text("🔒")
        cr.restore()
