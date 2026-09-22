"""Dibujo vectorial de reloj de buceo (estilo diver) con Cairo.

100% procedural, sin imagenes externas ni marcas registradas.
Funcion: draw_diver(cr, w, h, hour, minute, second_float, day)
"""

import math


def _circle(cr, cx, cy, r):
    cr.arc(cx, cy, r, 0, 2 * math.pi)


def _ring_gradient(cx, cy, r_outer, light_x=-0.35, light_y=-0.35):
    import cairo
    g = cairo.RadialGradient(
        cx + r_outer * light_x, cy + r_outer * light_y, r_outer * 0.1,
        cx, cy, r_outer,
    )
    # Oro a juego con la Agenda de Lujo (GOLD_LIGHT / GOLD / GOLD_DARK)
    g.add_color_stop_rgb(0.0, 0.98, 0.90, 0.60)
    g.add_color_stop_rgb(0.45, 0.79, 0.64, 0.15)
    g.add_color_stop_rgb(0.75, 0.93, 0.82, 0.45)
    g.add_color_stop_rgb(1.0, 0.48, 0.37, 0.10)
    return g


def _text_centered(cr, cx, y, text, size, color=(0.92, 0.92, 0.9), bold=True, spacing=1.0):
    cr.save()
    cr.select_font_face("Sans", 0, 1 if bold else 0)
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(cx - ext.width / 2 - ext.x_bearing, y)
    cr.show_text(text)
    cr.restore()


def _draw_dive_mark(cr, cx, y, s):
    """Marca generica de buceo: triangulo de bisel."""
    cr.save()
    cr.set_source_rgb(0.92, 0.92, 0.9)
    cr.set_line_width(max(1.0, s * 0.14))
    cr.set_line_join(2)
    cr.move_to(cx, y - s)
    cr.line_to(cx - s, y + s * 0.7)
    cr.line_to(cx + s, y + s * 0.7)
    cr.close_path()
    cr.stroke()
    cr.restore()


def _draw_hand(cr, cx, cy, angle_rad, length, width, color, tail=0.0):
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(angle_rad)
    cr.set_source_rgb(*color)
    cr.set_line_cap(1)
    cr.set_line_width(width)
    cr.move_to(0, tail)
    cr.line_to(0, -length)
    cr.stroke()
    cr.restore()


def draw_diver(cr, w, h, hour, minute, second_float, day):
    import cairo

    size = min(w, h)
    if size <= 0:
        return
    cx, cy = w / 2.0, h / 2.0
    R = size / 2.0 - 4  # radio caja

    # Fondo transparente
    cr.set_operator(cairo.OPERATOR_OVER)

    # --- Sombra exterior suave ---
    cr.save()
    _circle(cr, cx, cy + R * 0.03, R * 1.0)
    cr.set_source_rgba(0, 0, 0, 0.35)
    cr.fill()
    cr.restore()

    # --- Caja dorada (a juego con la agenda) ---
    cr.save()
    _circle(cr, cx, cy, R)
    cr.set_source(_ring_gradient(cx, cy, R))
    cr.fill()
    # borde fino oscuro
    _circle(cr, cx, cy, R)
    cr.set_source_rgb(0.30, 0.22, 0.06)
    cr.set_line_width(max(1.5, R * 0.012))
    cr.stroke()
    cr.restore()

    # --- Corona lateral (derecha, a las 3) ---
    cr.save()
    cw, chh = R * 0.10, R * 0.14
    cr.set_source_rgb(0.79, 0.64, 0.15)
    cr.rectangle(cx + R - 1, cy - chh / 2, cw, chh)
    cr.fill()
    cr.set_source_rgb(0.48, 0.37, 0.10)
    for i in range(3):
        yy = cy - chh / 2 + (i + 0.5) * chh / 3
        cr.move_to(cx + R + 1, yy)
        cr.line_to(cx + R + cw - 1, yy)
        cr.set_line_width(1)
        cr.stroke()
    cr.restore()

    r_bezel_out = R * 0.94
    r_bezel_in = R * 0.76
    r_dial = R * 0.76

    # --- Bisel negro ---
    cr.save()
    _circle(cr, cx, cy, r_bezel_out)
    g = cairo.RadialGradient(cx, cy, r_bezel_in * 0.5, cx, cy, r_bezel_out)
    g.add_color_stop_rgb(0, 0.10, 0.11, 0.13)
    g.add_color_stop_rgb(1, 0.02, 0.025, 0.03)
    cr.set_source(g)
    cr.fill()
    # anillo dorado entre bisel y caja
    _circle(cr, cx, cy, r_bezel_out)
    cr.set_source_rgb(0.93, 0.82, 0.45)
    cr.set_line_width(max(1.0, R * 0.008))
    cr.stroke()
    _circle(cr, cx, cy, r_bezel_in)
    cr.set_source_rgb(0.79, 0.64, 0.15)
    cr.set_line_width(max(1.0, R * 0.008))
    cr.stroke()
    cr.restore()

    # --- Marcas del bisel (60) + numeros ---
    cr.save()
    cr.translate(cx, cy)
    for i in range(60):
        if i in (10, 20, 30, 40, 50):
            continue  # ahi va el numero, estilo diver clasico
        a = i * 6 * math.pi / 180
        is_five = (i % 5 == 0)
        # solo primeros 15 min marcados fuerte; resto sutil
        r1 = r_bezel_out * 0.97 if is_five else r_bezel_out * 0.985
        r2 = r_bezel_out * 0.90 if is_five else r_bezel_out * 0.95
        cr.save()
        cr.rotate(a)
        cr.set_source_rgb(0.9, 0.9, 0.88)
        cr.set_line_width(r_bezel_out * 0.022 if is_five else r_bezel_out * 0.01)
        cr.set_line_cap(1)
        cr.move_to(0, -r1)
        cr.line_to(0, -r2)
        cr.stroke()
        cr.restore()
    # triangulo a las 12
    cr.save()
    cr.rotate(0)
    cr.move_to(0, -r_bezel_out * 0.985)
    cr.line_to(-r_bezel_out * 0.045, -r_bezel_out * 0.895)
    cr.line_to(r_bezel_out * 0.045, -r_bezel_out * 0.895)
    cr.close_path()
    cr.set_source_rgb(0.9, 0.9, 0.88)
    cr.fill()
    cr.restore()
    # numeros 10..50 (centrados en el anillo del bisel)
    cr.select_font_face("Sans", 0, 1)
    cr.set_font_size(r_bezel_out * 0.095)
    cr.set_source_rgb(0.88, 0.88, 0.86)
    for num, deg in [(10, 60), (20, 120), (30, 180), (40, 240), (50, 300)]:
        a = math.radians(deg)
        tx = math.sin(a) * r_bezel_out * 0.90
        ty = -math.cos(a) * r_bezel_out * 0.90
        t = str(num)
        ext = cr.text_extents(t)
        cr.move_to(tx - ext.width / 2 - ext.x_bearing, ty + ext.height / 2)
        cr.show_text(t)
    cr.restore()

    # --- Esfera ---
    cr.save()
    _circle(cr, cx, cy, r_dial)
    g = cairo.RadialGradient(cx - r_dial * 0.3, cy - r_dial * 0.3, r_dial * 0.1, cx, cy, r_dial)
    g.add_color_stop_rgb(0, 0.10, 0.12, 0.14)
    g.add_color_stop_rgb(1, 0.0, 0.005, 0.01)
    cr.set_source(g)
    cr.fill()
    cr.restore()

    # --- Minutero perimetral de la esfera ---
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

    # --- Indices con lume ---
    def lume_dot(x, y, r):
        _circle(cr, x, y, r * 1.28)
        cr.set_source_rgb(0.55, 0.57, 0.58)
        cr.fill()
        _circle(cr, x, y, r)
        cr.set_source_rgb(0.93, 0.95, 0.88)
        cr.fill()

    cr.save()
    for i in range(12):
        if i == 2:  # fecha a las 3, saltar indice
            continue
        a = i * 30 * math.pi / 180
        rr = r_dial * 0.78
        x = cx + math.sin(a) * rr
        y = cy - math.cos(a) * rr
        cr.save()
        cr.translate(x, y)
        cr.rotate(a)
        if i == 0:  # triangulo 12
            s = r_dial * 0.085
            cr.move_to(0, -s)
            cr.line_to(-s * 0.9, s * 0.8)
            cr.line_to(s * 0.9, s * 0.8)
            cr.close_path()
            cr.set_source_rgb(0.55, 0.57, 0.58)
            cr.fill()
            s2 = s * 0.72
            cr.move_to(0, -s2)
            cr.line_to(-s2 * 0.9, s2 * 0.8)
            cr.line_to(s2 * 0.9, s2 * 0.8)
            cr.close_path()
            cr.set_source_rgb(0.93, 0.95, 0.88)
            cr.fill()
        elif i in (5, 8):  # rectangulos 6 y 9
            ww, hh = r_dial * 0.10, r_dial * 0.16
            cr.rectangle(-ww / 2 - 1.5, -hh / 2 - 1.5, ww + 3, hh + 3)
            cr.set_source_rgb(0.55, 0.57, 0.58)
            cr.fill()
            cr.rectangle(-ww / 2, -hh / 2, ww, hh)
            cr.set_source_rgb(0.93, 0.95, 0.88)
            cr.fill()
        else:
            lume_dot(0, 0, r_dial * 0.055)
        cr.restore()
    cr.restore()

    # --- Textos esfera ---
    _draw_dive_mark(cr, cx, cy - r_dial * 0.36, r_dial * 0.05)
    _text_centered(cr, cx, cy - r_dial * 0.20, "DIVER", r_dial * 0.085)
    _text_centered(cr, cx, cy - r_dial * 0.08, "AUTOMATIC", r_dial * 0.045, bold=False)
    _text_centered(cr, cx, cy + r_dial * 0.30, "SUBMARINOS", r_dial * 0.07)
    _text_centered(cr, cx, cy + r_dial * 0.40, "1000ft = 300m", r_dial * 0.042, bold=False)

    # --- Ventana de fecha a las 3 ---
    cr.save()
    fw, fh = r_dial * 0.20, r_dial * 0.16
    fx = cx + r_dial * 0.52
    fy = cy
    cr.rectangle(fx - fw / 2, fy - fh / 2, fw, fh)
    cr.set_source_rgb(0.92, 0.93, 0.90)
    cr.fill()
    cr.rectangle(fx - fw / 2, fy - fh / 2, fw, fh)
    cr.set_source_rgb(0.2, 0.2, 0.22)
    cr.set_line_width(1.2)
    cr.stroke()
    _text_centered(cr, fx, fy + fh * 0.28, str(day), fh * 0.72, color=(0.05, 0.05, 0.06))
    # brillo lupa
    cr.rectangle(fx - fw / 2, fy - fh / 2, fw, fh * 0.35)
    cr.set_source_rgba(0.6, 0.75, 0.95, 0.18)
    cr.fill()
    cr.restore()

    # --- Manecillas ---
    sec_a = (second_float / 60.0) * 2 * math.pi
    min_a = ((minute + second_float / 60.0) / 60.0) * 2 * math.pi
    hr_a = (((hour % 12) + minute / 60.0) / 12.0) * 2 * math.pi

    # hora Mercedes
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(hr_a)
    hl, hw = r_dial * 0.48, r_dial * 0.075
    cr.set_source_rgb(0.93, 0.95, 0.88)
    cr.set_line_cap(1)
    cr.set_line_width(hw)
    cr.move_to(0, r_dial * 0.12)
    cr.line_to(0, -hl)
    cr.stroke()
    # anillo mercedes
    _circle(cr, 0, -hl * 0.62, hw * 0.95)
    cr.set_source_rgb(0.93, 0.95, 0.88)
    cr.fill()
    _circle(cr, 0, -hl * 0.62, hw * 0.62)
    cr.set_source_rgb(0.05, 0.05, 0.06)
    cr.fill()
    # radios mercedes
    cr.set_source_rgb(0.93, 0.95, 0.88)
    cr.set_line_width(hw * 0.28)
    for deg in (0, 120, 240):
        a = math.radians(deg)
        cr.move_to(0, -hl * 0.62)
        cr.line_to(math.sin(a) * hw * 0.62, -hl * 0.62 - math.cos(a) * hw * 0.62)
        cr.stroke()
    cr.restore()

    # minuto
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(min_a)
    ml, mw = r_dial * 0.72, r_dial * 0.055
    cr.set_source_rgb(0.93, 0.95, 0.88)
    cr.set_line_cap(1)
    cr.set_line_width(mw)
    cr.move_to(0, r_dial * 0.12)
    cr.line_to(0, -ml)
    cr.stroke()
    cr.restore()

    # segundo fino + lume
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(sec_a)
    cr.set_source_rgb(0.85, 0.87, 0.85)
    cr.set_line_width(max(1.2, r_dial * 0.014))
    cr.move_to(0, r_dial * 0.18)
    cr.line_to(0, -r_dial * 0.80)
    cr.stroke()
    _circle(cr, 0, -r_dial * 0.55, r_dial * 0.045)
    cr.set_source_rgb(0.93, 0.95, 0.88)
    cr.fill()
    _circle(cr, 0, -r_dial * 0.55, r_dial * 0.045)
    cr.set_source_rgb(0.3, 0.3, 0.3)
    cr.set_line_width(1)
    cr.stroke()
    cr.restore()

    # --- Eje central ---
    _circle(cr, cx, cy, r_dial * 0.035)
    cr.set_source_rgb(0.93, 0.82, 0.45)
    cr.fill()
    _circle(cr, cx, cy, r_dial * 0.018)
    cr.set_source_rgb(0.1, 0.1, 0.11)
    cr.fill()

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
