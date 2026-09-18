"""Dibujo vectorial estilo cronografo mecanico con Cairo.

100% procedural, sin imagenes externas. Misma paleta oro/cuero que el
Rolex Submariner y la Agenda de Lujo.

Funciones:
  draw_chrono(cr, w, h, elapsed_s, running, locked)
  chrono_button_zones(w, h) -> {"start": (cx, cy, r), "reset": (cx, cy, r)}
  format_elapsed(elapsed_s) -> "HH:MM:SS.D"
"""

import math


GOLD_LIGHT = (0.98, 0.90, 0.60)
GOLD = (0.79, 0.64, 0.15)
GOLD_DARK = (0.48, 0.37, 0.10)
LUME = (0.93, 0.95, 0.88)
LUME_DIM = (0.55, 0.57, 0.58)
GREEN = (0.25, 0.75, 0.35)
RED = (0.85, 0.25, 0.20)

# Pushers a las 2 (start/stop) y a las 4 (reset), angulos desde las 12.
START_ANGLE = math.radians(60)
RESET_ANGLE = math.radians(120)


def _circle(cr, cx, cy, r):
    cr.new_sub_path()
    cr.arc(cx, cy, r, 0, 2 * math.pi)


def _round_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _ring_gradient(cx, cy, r_outer):
    import cairo
    g = cairo.RadialGradient(
        cx - r_outer * 0.35, cy - r_outer * 0.35, r_outer * 0.1,
        cx, cy, r_outer,
    )
    g.add_color_stop_rgb(0.0, *GOLD_LIGHT)
    g.add_color_stop_rgb(0.45, *GOLD)
    g.add_color_stop_rgb(0.75, 0.93, 0.82, 0.45)
    g.add_color_stop_rgb(1.0, *GOLD_DARK)
    return g


def _text_centered(cr, cx, y, text, size, color=LUME, bold=True):
    cr.save()
    cr.select_font_face("Sans", 0, 1 if bold else 0)
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(cx - ext.width / 2 - ext.x_bearing, y)
    cr.show_text(text)
    cr.restore()


def format_elapsed(elapsed_s):
    """HH:MM:SS.D (las horas no se recortan a 12 en el digital).

    Redondea a decimas desde el total para no mostrar .6 cuando el float
    guarda .6999... (p. ej. 22.7).
    """
    tenths = int(round(max(0.0, float(elapsed_s)) * 10))
    d = tenths % 10
    total_s = tenths // 10
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{d}"


def _geometry(size):
    """Geometria compartida por dibujo y zonas de botones (coords logicas)."""
    cx = cy = size / 2.0
    push_margin = size * 0.055
    R = size / 2.0 - 4 - push_margin
    r_dial = R * 0.76
    geo = {
        "cx": cx, "cy": cy, "R": R, "r_dial": r_dial,
        # subesferas: (dx, dy, radio) relativos a r_dial
        "tenths": (0.0, -0.42, 0.22),
        "minutes": (-0.44, 0.18, 0.22),
        "hours": (0.44, 0.18, 0.22),
    }
    for name, angle in (("start", START_ANGLE), ("reset", RESET_ANGLE)):
        px = cx + math.sin(angle) * (R + push_margin * 0.45)
        py = cy - math.cos(angle) * (R + push_margin * 0.45)
        geo[name] = (px, py, push_margin * 0.55, angle)
    return geo


def chrono_button_zones(w, h):
    """Centros y radio tactil de los pushers (para los Gtk.Button overlay)."""
    size = min(w, h)
    if size <= 0:
        return {"start": (0, 0, 18), "reset": (0, 0, 18)}
    geo = _geometry(size)
    out = {}
    for name in ("start", "reset"):
        px, py, _half, _angle = geo[name]
        # Radio tactil: comodo pero sin salirse de la ventana.
        edge = min(px, py, size - px, size - py) - 1
        r = max(10.0, min(size * 0.07, edge))
        out[name] = (px, py, r)
    return out


def _draw_subdial(cr, cx, cy, r, ticks, numerals, hand_angle, label=None):
    # fondo hundido
    _circle(cr, cx, cy, r)
    cr.set_source_rgb(0.03, 0.035, 0.04)
    cr.fill()
    _circle(cr, cx, cy, r)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(max(1.0, r * 0.05))
    cr.stroke()
    # ticks
    cr.save()
    cr.translate(cx, cy)
    for i in range(ticks):
        a = i * 2 * math.pi / ticks
        cr.save()
        cr.rotate(a)
        big = (i % (ticks // max(1, len(numerals))) == 0) if numerals else False
        cr.set_source_rgb(*LUME)
        cr.set_line_width(r * 0.05 if big else r * 0.028)
        cr.move_to(0, -r * 0.92)
        cr.line_to(0, -r * (0.78 if big else 0.84))
        cr.stroke()
        cr.restore()
    cr.restore()
    # numerales
    cr.save()
    cr.select_font_face("Sans", 0, 1)
    cr.set_font_size(r * 0.30)
    cr.set_source_rgb(*LUME)
    for value, frac in numerals:
        a = frac * 2 * math.pi
        tx = cx + math.sin(a) * r * 0.55
        ty = cy - math.cos(a) * r * 0.55
        t = str(value)
        ext = cr.text_extents(t)
        cr.move_to(tx - ext.width / 2 - ext.x_bearing, ty + ext.height / 2)
        cr.show_text(t)
    cr.restore()
    # aguja dorada fina + contrapeso
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(hand_angle)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(max(1.0, r * 0.06))
    cr.set_line_cap(1)
    cr.move_to(0, r * 0.25)
    cr.line_to(0, -r * 0.80)
    cr.stroke()
    _circle(cr, 0, r * 0.30, r * 0.10)
    cr.set_source_rgb(*GOLD)
    cr.fill()
    cr.restore()
    _circle(cr, cx, cy, r * 0.07)
    cr.set_source_rgb(*GOLD_DARK)
    cr.fill()
    if label:
        _text_centered(cr, cx, cy + r * 1.32, label, r * 0.24, color=LUME_DIM,
                       bold=False)


def draw_chrono(cr, w, h, elapsed_s, running, locked=False):
    import cairo

    size = min(w, h)
    if size <= 0:
        return
    geo = _geometry(size)
    cx, cy, R, r_dial = geo["cx"], geo["cy"], geo["R"], geo["r_dial"]
    e = max(0.0, float(elapsed_s))

    cr.set_operator(cairo.OPERATOR_OVER)

    # --- Sombra exterior suave ---
    cr.save()
    _circle(cr, cx, cy + R * 0.03, R)
    cr.set_source_rgba(0, 0, 0, 0.35)
    cr.fill()
    cr.restore()

    # --- Caja dorada ---
    cr.save()
    _circle(cr, cx, cy, R)
    cr.set_source(_ring_gradient(cx, cy, R))
    cr.fill()
    _circle(cr, cx, cy, R)
    cr.set_source_rgb(0.30, 0.22, 0.06)
    cr.set_line_width(max(1.5, R * 0.012))
    cr.stroke()
    cr.restore()

    # --- Corona a las 3 ---
    cr.save()
    cw, chh = R * 0.08, R * 0.12
    cr.set_source_rgb(*GOLD)
    cr.rectangle(cx + R - 1, cy - chh / 2, cw, chh)
    cr.fill()
    cr.set_source_rgb(*GOLD_DARK)
    for i in range(3):
        yy = cy - chh / 2 + (i + 0.5) * chh / 3
        cr.move_to(cx + R + 1, yy)
        cr.line_to(cx + R + cw - 1, yy)
        cr.set_line_width(1)
        cr.stroke()
    cr.restore()

    # --- Pushers (start arriba, reset abajo) ---
    for name, ring in (("start", GREEN if not running else RED),
                       ("reset", GOLD)):
        px, py, half, angle = geo[name]
        dimmed = (name == "reset" and running)
        cr.save()
        cr.translate(px, py)
        cr.rotate(angle)
        _round_rect(cr, -half * 0.55, -half, half * 1.1, half * 2, half * 0.4)
        cr.set_source_rgb(0.12, 0.12, 0.13)
        cr.fill()
        _round_rect(cr, -half * 0.55, -half, half * 1.1, half * 2, half * 0.4)
        if dimmed:
            cr.set_source_rgb(*LUME_DIM)
        else:
            cr.set_source_rgb(*ring)
        cr.set_line_width(max(1.5, half * 0.16))
        cr.stroke()
        # capuchon dorado
        _round_rect(cr, -half * 0.30, -half * 0.72, half * 0.6, half * 1.44,
                    half * 0.28)
        if dimmed:
            cr.set_source_rgb(0.35, 0.35, 0.36)
        else:
            cr.set_source_rgb(*GOLD)
        cr.fill()
        cr.restore()

    # --- Bisel negro con 60 marcas ---
    r_bezel_out, r_bezel_in = R * 0.94, r_dial
    cr.save()
    _circle(cr, cx, cy, r_bezel_out)
    g = cairo.RadialGradient(cx, cy, r_bezel_in * 0.5, cx, cy, r_bezel_out)
    g.add_color_stop_rgb(0, 0.10, 0.11, 0.13)
    g.add_color_stop_rgb(1, 0.02, 0.025, 0.03)
    cr.set_source(g)
    cr.fill()
    _circle(cr, cx, cy, r_bezel_out)
    cr.set_source_rgb(0.93, 0.82, 0.45)
    cr.set_line_width(max(1.0, R * 0.008))
    cr.stroke()
    _circle(cr, cx, cy, r_bezel_in)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(max(1.0, R * 0.008))
    cr.stroke()
    cr.restore()

    cr.save()
    cr.translate(cx, cy)
    for i in range(60):
        a = i * 6 * math.pi / 180
        cr.save()
        cr.rotate(a)
        big = (i % 5 == 0)
        cr.set_source_rgb(0.9, 0.9, 0.88)
        cr.set_line_width(r_bezel_out * 0.022 if big else r_bezel_out * 0.01)
        cr.set_line_cap(1)
        cr.move_to(0, -r_bezel_out * (0.97 if big else 0.985))
        cr.line_to(0, -r_bezel_out * (0.90 if big else 0.95))
        cr.stroke()
        cr.restore()
    # triangulo a las 12
    cr.save()
    cr.move_to(0, -r_bezel_out * 0.985)
    cr.line_to(-r_bezel_out * 0.045, -r_bezel_out * 0.895)
    cr.line_to(r_bezel_out * 0.045, -r_bezel_out * 0.895)
    cr.close_path()
    cr.set_source_rgb(0.9, 0.9, 0.88)
    cr.fill()
    cr.restore()
    cr.restore()

    # --- Esfera ---
    cr.save()
    _circle(cr, cx, cy, r_dial)
    g = cairo.RadialGradient(cx - r_dial * 0.3, cy - r_dial * 0.3,
                             r_dial * 0.1, cx, cy, r_dial)
    g.add_color_stop_rgb(0, 0.10, 0.12, 0.14)
    g.add_color_stop_rgb(1, 0.0, 0.005, 0.01)
    cr.set_source(g)
    cr.fill()
    cr.restore()

    # --- Minutero perimetral ---
    cr.save()
    cr.translate(cx, cy)
    for i in range(60):
        a = i * 6 * math.pi / 180
        cr.save()
        cr.rotate(a)
        big = (i % 5 == 0)
        cr.set_source_rgb(0.85, 0.85, 0.83)
        cr.set_line_width(r_dial * 0.012 if big else r_dial * 0.006)
        cr.move_to(0, -r_dial * 0.985)
        cr.line_to(0, -r_dial * (0.94 if big else 0.96))
        cr.stroke()
        cr.restore()
    cr.restore()

    # --- Textos ---
    _text_centered(cr, cx, cy - r_dial * 0.80, "CRONÓGRAFO", r_dial * 0.075)
    _text_centered(cr, cx, cy - r_dial * 0.70, "MECÁNICO · 1/10 S",
                   r_dial * 0.040, bold=False)

    # --- Subesferas ---
    tdx, tdy, tdr = geo["tenths"]
    _draw_subdial(cr, cx + tdx * r_dial, cy + tdy * r_dial, tdr * r_dial,
                  10, [(2, 0.2), (4, 0.4), (6, 0.6), (8, 0.8)],
                  (e % 1.0) * 2 * math.pi)
    mdx, mdy, mdr = geo["minutes"]
    _draw_subdial(cr, cx + mdx * r_dial, cy + mdy * r_dial, mdr * r_dial,
                  30, [(10, 10 / 30), (20, 20 / 30), (30, 0.0)],
                  ((e / 60.0) % 30 / 30.0) * 2 * math.pi, label="MIN")
    hdx, hdy, hdr = geo["hours"]
    _draw_subdial(cr, cx + hdx * r_dial, cy + hdy * r_dial, hdr * r_dial,
                  12, [(3, 0.25), (6, 0.5), (9, 0.75), (12, 0.0)],
                  ((e / 3600.0) % 12 / 12.0) * 2 * math.pi, label="HRS")

    # --- Ventana digital HH:MM:SS.D ---
    cr.save()
    fw, fh = r_dial * 1.05, r_dial * 0.22
    fx, fy = cx, cy + r_dial * 0.60
    _round_rect(cr, fx - fw / 2, fy - fh / 2, fw, fh, fh * 0.25)
    cr.set_source_rgb(0.02, 0.025, 0.03)
    cr.fill()
    _round_rect(cr, fx - fw / 2, fy - fh / 2, fw, fh, fh * 0.25)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(max(1.0, r_dial * 0.008))
    cr.stroke()
    _text_centered(cr, fx, fy + fh * 0.30, format_elapsed(e), fh * 0.62,
                   color=LUME)
    cr.restore()

    # --- Aguja central: segundos del crono ---
    sec_a = ((e % 60.0) / 60.0) * 2 * math.pi
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(sec_a)
    cr.set_source_rgb(*LUME)
    cr.set_line_width(max(1.2, r_dial * 0.016))
    cr.set_line_cap(1)
    cr.move_to(0, r_dial * 0.20)
    cr.line_to(0, -r_dial * 0.82)
    cr.stroke()
    # contrapeso dorado
    _circle(cr, 0, r_dial * 0.28, r_dial * 0.05)
    cr.set_source_rgb(*GOLD)
    cr.fill()
    cr.restore()

    # --- Eje central ---
    _circle(cr, cx, cy, r_dial * 0.035)
    cr.set_source_rgb(0.93, 0.82, 0.45)
    cr.fill()
    _circle(cr, cx, cy, r_dial * 0.018)
    cr.set_source_rgb(0.1, 0.1, 0.11)
    cr.fill()

    # --- Candadito si bloqueado (abajo-derecha) ---
    if locked:
        cr.save()
        lx, ly = w - 32, h - 26
        cr.set_source_rgb(*GOLD)
        cr.set_line_width(2.0)
        cr.set_line_cap(1)
        cr.new_sub_path()
        cr.arc(lx, ly - 2, 6, math.pi, 2 * math.pi)
        cr.stroke()
        _round_rect(cr, lx - 9, ly - 2, 18, 13, 3)
        cr.stroke()
        cr.new_sub_path()
        cr.arc(lx, ly + 2.5, 1.8, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

    # --- Reflejo cristal ---
    cr.save()
    _circle(cr, cx, cy, r_dial)
    cr.clip()
    cr.translate(cx, cy)
    cr.rotate(-0.5)
    g = cairo.LinearGradient(0, -r_dial, 0, r_dial)
    g.add_color_stop_rgba(0, 1, 1, 1, 0.10)
    g.add_color_stop_rgba(0.35, 1, 1, 1, 0.02)
    g.add_color_stop_rgba(0.6, 1, 1, 1, 0.0)
    cr.rectangle(-r_dial, -r_dial, r_dial * 2, r_dial * 2)
    cr.set_source(g)
    cr.fill()
    cr.restore()
