"""Dibujo vectorial de agenda-calendario de lujo con Cairo.

100% procedural, sin imagenes externas.
Funcion: draw_agenda(cr, w, h, year, month, today_ymd, monday_first=True)
  - today_ymd: (y, m, d) del dia actual del sistema (para resaltar).
  - year/month: mes visible.
"""

import calendar
import math

GOLD = (0.79, 0.64, 0.15)
GOLD_LIGHT = (0.93, 0.82, 0.45)
GOLD_DARK = (0.48, 0.37, 0.10)
CREAM = (0.92, 0.89, 0.80)
MUTED = (0.55, 0.52, 0.45)
SUNDAY = (0.85, 0.55, 0.45)

MESES = [
    "", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]
DIAS_LARGOS = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]


def _rr(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _text_centered(cr, cx, y, text, size, color, serif=True, bold=True):
    cr.save()
    cr.select_font_face(
        "Serif" if serif else "Sans", 0, 1 if bold else 0,
    )
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(cx - ext.width / 2 - ext.x_bearing, y)
    cr.show_text(text)
    cr.restore()


def header_arrow_zones(w, h):
    """Zonas clicables (coords lógicas) de los botones ‹ › y del footer 'hoy'.

    Devuelve dict con 'prev': (cx, cy, r), 'next': (cx, cy, r),
    'today': (x, y, w, h_rect). Debe coincidir con draw_agenda().
    """
    pad = 6
    x0, y0, ww = pad, pad, w - pad * 2
    hy = y0 + max(30, h * 0.09)
    cy = hy - 8
    r = max(8, min(15, ww * 0.045))
    offset = max(20, ww * 0.08)
    return {
        "prev": (x0 + offset, cy, r),
        "next": (x0 + ww - offset, cy, r),
        "today": (x0 + 18, y0 + (h - pad * 2) - max(30, h * 0.09), ww - 36, max(20, h * 0.07)),
    }


def _draw_arrow_button(cr, cx, cy, r, direction):
    """Botón circular dorado con chevrón ‹ / ›."""
    import cairo
    # new_sub_path antes de cada arc: evita que cairo dibuje una línea
    # fantasma desde el current point residual hasta el inicio del arco.
    cr.save()
    cr.new_sub_path()
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    g = cairo.RadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.2, cx, cy, r)
    g.add_color_stop_rgb(0, 0.16, 0.15, 0.13)
    g.add_color_stop_rgb(1, 0.05, 0.045, 0.05)
    cr.set_source(g)
    cr.fill_preserve()
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(1.6)
    cr.stroke()
    # filete interior fino
    cr.new_sub_path()
    cr.arc(cx, cy, r - 4.5, 0, 2 * math.pi)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(0.8)
    cr.stroke()
    # chevrón
    s = r * 0.42
    cr.set_source_rgb(*GOLD_LIGHT)
    cr.set_line_width(2.2)
    cr.set_line_cap(1)
    cr.set_line_join(1)
    if direction == "prev":
        cr.move_to(cx + s * 0.5, cy - s)
        cr.line_to(cx - s * 0.6, cy)
        cr.line_to(cx + s * 0.5, cy + s)
    else:
        cr.move_to(cx - s * 0.5, cy - s)
        cr.line_to(cx + s * 0.6, cy)
        cr.line_to(cx - s * 0.5, cy + s)
    cr.stroke()
    cr.restore()


def draw_agenda(cr, w, h, year, month, today_ymd, monday_first=True, locked=False):
    import cairo

    if w <= 0 or h <= 0:
        return
    cr.set_operator(cairo.OPERATOR_OVER)

    pad = 6
    # --- Sombra exterior ---
    cr.save()
    _rr(cr, pad, pad + 4, w - pad * 2, h - pad * 2, 18)
    cr.set_source_rgba(0, 0, 0, 0.4)
    cr.fill()
    cr.restore()

    x0, y0, ww, hh = pad, pad, w - pad * 2, h - pad * 2

    # --- Cuerpo cuero negro ---
    cr.save()
    _rr(cr, x0, y0, ww, hh, 18)
    g = cairo.RadialGradient(
        x0 + ww * 0.35, y0 + hh * 0.25, min(ww, hh) * 0.1,
        x0 + ww / 2, y0 + hh / 2, max(ww, hh) * 0.75,
    )
    g.add_color_stop_rgb(0, 0.11, 0.115, 0.13)
    g.add_color_stop_rgb(0.6, 0.05, 0.052, 0.06)
    g.add_color_stop_rgb(1, 0.015, 0.016, 0.02)
    cr.set_source(g)
    cr.fill()
    cr.restore()

    # --- Marco dorado doble ---
    cr.save()
    _rr(cr, x0, y0, ww, hh, 18)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(2.5)
    cr.stroke()
    _rr(cr, x0 + 7, y0 + 7, ww - 14, hh - 14, 13)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1.0)
    cr.stroke()
    cr.restore()

    # --- Remaches esquinas ---
    cr.save()
    for cx, cy in (
        (x0 + 14, y0 + 14), (x0 + ww - 14, y0 + 14),
        (x0 + 14, y0 + hh - 14), (x0 + ww - 14, y0 + hh - 14),
    ):
        cr.new_sub_path()
        cr.arc(cx, cy, 3.2, 0, 2 * math.pi)
        cr.set_source_rgb(*GOLD)
        cr.fill()
        cr.new_sub_path()
        cr.arc(cx - 1, cy - 1, 1.1, 0, 2 * math.pi)
        cr.set_source_rgb(1, 0.95, 0.7)
        cr.fill()
    cr.restore()

    inner_x = x0 + 18
    inner_w = ww - 36

    # --- Header MES AÑO ---
    hy = y0 + max(30, hh * 0.09)
    header_size = max(8, min(ww * 0.060, 24))
    _text_centered(
        cr, x0 + ww / 2, hy, f"{MESES[month]} {year}",
        header_size, GOLD_LIGHT,
    )
    # botones dorados mes anterior / siguiente
    zones = header_arrow_zones(w, h)
    _draw_arrow_button(cr, *zones["prev"], "prev")
    _draw_arrow_button(cr, *zones["next"], "next")
    # filete con rombo
    cr.save()
    ly = hy + 14
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1.0)
    cr.move_to(inner_x, ly)
    cr.line_to(x0 + ww / 2 - 14, ly)
    cr.move_to(x0 + ww / 2 + 14, ly)
    cr.line_to(x0 + ww - 18, ly)
    cr.stroke()
    cxm = x0 + ww / 2
    cr.move_to(cxm, ly - 5)
    cr.line_to(cxm + 5, ly)
    cr.line_to(cxm, ly + 5)
    cr.line_to(cxm - 5, ly)
    cr.close_path()
    cr.set_source_rgb(*GOLD)
    cr.fill()
    cr.restore()

    # --- Nombres dias semana ---
    week = ["L", "M", "M", "J", "V", "S", "D"] if monday_first else ["D", "L", "M", "M", "J", "V", "S"]
    grid_top = ly + max(18, hh * 0.05)
    grid_x = inner_x
    grid_w = inner_w
    cell_w = grid_w / 7.0
    cr.save()
    cr.select_font_face("Serif", 0, 1)
    cr.set_font_size(max(6, min(cell_w * 0.32, 15)))
    cr.set_source_rgb(*MUTED)
    for i, name in enumerate(week):
        ext = cr.text_extents(name)
        cr.move_to(
            grid_x + i * cell_w + cell_w / 2 - ext.width / 2 - ext.x_bearing,
            grid_top,
        )
        cr.show_text(name)
    cr.restore()

    # --- Rejilla dias ---
    first_weekday, ndays = calendar.monthrange(year, month)  # lunes=0
    if monday_first:
        offset = first_weekday
    else:
        offset = (first_weekday + 1) % 7
    prev_days = calendar.monthrange(
        year - 1 if month == 1 else year, 12 if month == 1 else month - 1,
    )[1]

    rows = 6
    footer_h = 64
    grid_h = (y0 + hh - footer_h) - (grid_top + 12)
    cell_h = grid_h / rows
    ty, tm, td = today_ymd

    cr.save()
    cr.select_font_face("Serif", 0, 0)
    for r in range(rows):
        for c in range(7):
            idx = r * 7 + c
            day_num = idx - offset + 1
            if day_num < 1:
                day_num = prev_days + day_num
                in_month = False
            elif day_num > ndays:
                day_num = day_num - ndays
                in_month = False
            else:
                in_month = True
            cell_cx = grid_x + c * cell_w + cell_w / 2
            cell_cy = grid_top + 12 + r * cell_h + cell_h / 2
            is_today = in_month and (year, month, day_num) == (ty, tm, td)
            # domingo: columna 6 (lunes primero) o 0 (domingo primero)
            is_sunday = (monday_first and c == 6) or (not monday_first and c == 0)

            day_font_size = max(5, min(cell_w, cell_h) * 0.38)
            if is_today:
                _rr(cr, cell_cx - cell_w * 0.42, cell_cy - cell_h * 0.40,
                    cell_w * 0.84, cell_h * 0.80, 8)
                tg = cairo.LinearGradient(0, cell_cy - cell_h / 2, 0, cell_cy + cell_h / 2)
                tg.add_color_stop_rgb(0, *GOLD_LIGHT)
                tg.add_color_stop_rgb(1, *GOLD)
                cr.set_source(tg)
                cr.fill()
                _text_centered(cr, cell_cx, cell_cy + cell_h * 0.13, str(day_num),
                               day_font_size, (0.08, 0.06, 0.02))
            else:
                if not in_month:
                    color = (0.32, 0.30, 0.27)
                elif is_sunday:
                    color = SUNDAY
                else:
                    color = CREAM
                _text_centered(cr, cell_cx, cell_cy + cell_h * 0.13, str(day_num),
                               max(5, min(cell_w, cell_h) * 0.36), color, bold=in_month)
    cr.restore()

    # --- Footer: fecha de hoy ---
    cr.save()
    fy = y0 + hh - max(24, hh * 0.07)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1.0)
    cr.move_to(inner_x, fy - max(10, hh * 0.03))
    cr.line_to(x0 + ww - 18, fy - max(10, hh * 0.03))
    cr.stroke()
    wd = calendar.weekday(ty, tm, td)
    wd_name = DIAS_LARGOS[wd]
    footer_size = max(6, min(ww * 0.042, 15))
    _text_centered(cr, x0 + ww / 2, fy,
                   f"Hoy · {wd_name} {td} de {MESES[tm].lower()}",
                   footer_size, GOLD_LIGHT, bold=False)
    # rombo dibujado con paths (el glifo ◇ no existe en todas las Serif)
    cr.save()
    dx, dy, ds = x0 + ww / 2, fy + 14, 5
    cr.move_to(dx, dy - ds)
    cr.line_to(dx + ds, dy)
    cr.line_to(dx, dy + ds)
    cr.line_to(dx - ds, dy)
    cr.close_path()
    cr.set_source_rgb(*GOLD_DARK)
    cr.fill()
    cr.restore()
    cr.restore()

    # --- Indicador de bloqueo: candadito dorado abajo-derecha ---
    if locked:
        cr.save()
        lx, ly = x0 + ww - 30, y0 + hh - 30
        cr.set_source_rgb(*GOLD)
        cr.set_line_width(2.0)
        cr.set_line_cap(1)
        # arco del candado
        cr.new_sub_path()
        cr.arc(lx, ly - 2, 6, math.pi, 2 * math.pi)
        cr.stroke()
        # cuerpo
        _rr(cr, lx - 9, ly - 2, 18, 13, 3)
        cr.stroke()
        # ojo de cerradura
        cr.new_sub_path()
        cr.arc(lx, ly + 2.5, 1.8, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

    # --- Reflejo cristal ---
    cr.save()
    _rr(cr, x0, y0, ww, hh, 18)
    cr.clip()
    cr.translate(x0 + ww / 2, y0 + hh / 2)
    cr.rotate(-0.45)
    g2 = cairo.LinearGradient(0, -hh, 0, hh)
    g2.add_color_stop_rgba(0, 1, 1, 1, 0.07)
    g2.add_color_stop_rgba(0.3, 1, 1, 1, 0.015)
    g2.add_color_stop_rgba(0.55, 1, 1, 1, 0.0)
    cr.rectangle(-ww, -hh, ww * 2, hh * 2)
    cr.set_source(g2)
    cr.fill()
    cr.restore()
