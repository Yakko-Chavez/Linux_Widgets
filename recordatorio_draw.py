"""Dibujo vectorial del widget Recordatorio Dorado (Cairo).

100% procedural, sin imagenes externas. Misma paleta oro/cuero que la
Agenda de Lujo y el Cronografo Mecanico.

Regla de la coleccion: la geometria de filas/botones se comparte entre
el dibujo y las zonas tactiles (una sola fuente de verdad).

Funciones:
  draw_recordatorio(cr, w, h, rems, now, locked, flash_phase=0)
  recordatorio_button_zones(w, h, rems)
  format_countdown(delta_s)
  parse_hhmm(s, now)
  now_epoch()
"""

import math
import re
import time

import cairo

import i18n

GOLD_LIGHT = (0.98, 0.90, 0.60)
GOLD = (0.79, 0.64, 0.15)
GOLD_DARK = (0.48, 0.37, 0.10)
LUME = (0.93, 0.95, 0.88)
LUME_DIM = (0.55, 0.57, 0.58)
RED = (0.85, 0.25, 0.20)

FONT = "DejaVu Sans"  # Sin la generica "Sans" faltan …, ✕ y ¡!

MAX_ROWS = 5

_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def now_epoch():
    return time.time()


def parse_hhmm(text, now=None):
    """'HH:MM' (24 h) -> epoch UTC de hoy; si ya paso, manana. None si invalido."""
    t = (text or "").strip()
    m = _HHMM.match(t)
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh > 23 or mm > 59:
        return None
    now = now_epoch() if now is None else float(now)
    lt = time.localtime(now)
    target = time.mktime((lt[0], lt[1], lt[2], hh, mm, 0, -1, lt[7], lt[8]))
    if target <= now:
        # misma hora ya paso: se interpreta como manana (DST consistente)
        target = time.mktime(
            (lt[0], lt[1], lt[2] + 1, hh, mm, 0, -1, lt[7], lt[8]))
    return target


def format_countdown(delta_s):
    """00:59 / 12:04 / 1h 02m / 23h 59m."""
    total = max(0, int(round(delta_s)))
    if total < 3600:
        return f"{(total // 60) % 60:02d}:{total % 60:02d}"
    h = total // 3600
    m = (total % 3600) // 60
    return i18n._("{h}h {m:02d}m", h=h, m=m)


def format_time_of_day(epoch, now=None):
    lt = time.localtime(epoch)
    return f"{lt[3]:02d}:{lt[4]:02d}"


def _rr(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _text(cr, x, y, text, size, color, bold=False, serif=False):
    cr.save()
    cr.select_font_face(FONT if not serif else "Serif", 0, 1 if bold else 0)
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(x - ext.x_bearing, y)
    cr.show_text(text)
    cr.restore()
    return ext


def _text_right(cr, x, y, text, size, color, bold=False):
    cr.save()
    cr.select_font_face(FONT, 0, 1 if bold else 0)
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(x - ext.width, y)
    cr.show_text(text)
    cr.restore()
    return ext


def _text_width(cr, text, size, bold=False):
    cr.save()
    cr.select_font_face(FONT, 0, 1 if bold else 0)
    cr.set_font_size(size)
    ext = cr.text_extents(text)
    cr.restore()
    return ext.width


def _truncate(cr, text, max_w, size, bold=False):
    """Recorta el texto con '…' para que quepa en max_w (o '' si cabe '…')."""
    if not text:
        return ""
    cr.save()
    cr.select_font_face(FONT, 0, 1 if bold else 0)
    cr.set_font_size(size)
    if cr.text_extents(text).width <= max_w:
        cr.restore()
        return text
    ell = i18n._("…")
    cr.restore()
    while text and text != ell:
        text = text[:-1]
        cand = text + ell
        cr.save()
        cr.select_font_face(FONT, 0, 1 if bold else 0)
        cr.set_font_size(size)
        ok = cr.text_extents(cand).width <= max_w
        cr.restore()
        if ok:
            return cand
    return ell


def geometry(w, h):
    """Geometria compartida por draw_recordatorio() y recordatorio_button_zones().

    Coords logicas. Filas visibles: MAX_ROWS o las que quepan.
    """
    pad = 6
    x0, y0, ww, hh = pad, pad, w - pad * 2, h - pad * 2
    header_y = y0 + max(28, hh * 0.085)
    dy = header_y + max(10, hh * 0.045)  # filete bajo el titulo
    list_top = dy + max(6, hh * 0.035)
    footer_h = max(30, hh * 0.11)
    list_bottom = y0 + hh - footer_h
    row_h = max(26, hh * 0.115)
    row_gap = max(6, hh * 0.022)
    n_fit = MAX_ROWS
    space = list_bottom - list_top
    if n_fit * row_h + (n_fit - 1) * row_gap > space and n_fit > 1:
        n_fit = max(1, int((space + row_gap) // (row_h + row_gap)))
    add_r = max(11, min(15, ww * 0.055))
    add_cx = x0 + max(22, ww * 0.085)
    add_cy = list_bottom + footer_h / 2
    return {
        "pad": pad, "x0": x0, "y0": y0, "ww": ww, "hh": hh,
        "header_y": header_y, "dy": dy,
        "list_top": list_top, "list_bottom": list_bottom,
        "row_h": row_h, "row_gap": row_gap, "n_fit": n_fit,
        "footer_y": list_bottom + footer_h * 0.62,
        "add": (add_cx, add_cy, add_r),
        "lock": (x0 + ww - 13, y0 + hh - 13),
    }


def row_rects(w, h, count):
    """Rects completos de fila: [(rx, ry, rw, rh)] para `count` filas."""
    geo = geometry(w, h)
    n = min(count, geo["n_fit"])
    out = []
    rw = geo["ww"] - 16
    rx = geo["x0"] + 8
    for i in range(n):
        ry = geo["list_top"] + i * (geo["row_h"] + geo["row_gap"])
        out.append((rx, ry, rw, geo["row_h"]))
    return out


def recordatorio_button_zones(w, h, rems):
    """Centros y radios tactiles: 'add' y 'del{i}' por fila visible.

    Recibe la lista ORDENADA de recordatorios (misma que dibuja).
    """
    geo = geometry(w, h)
    zones = {"add": geo["add"]}
    rects = row_rects(w, h, len(rems))
    for i, (rx, ry, rw, rh) in enumerate(rects):
        cx, cy = rx + rw - rh * 0.30, ry + rh / 2
        r = max(10.0, min(rh * 0.62, rh))
        zones[f"del{i}"] = (cx, cy, r)
    return zones


def _draw_bell(cr, cx, cy, s):
    """Campana dorada compacta (s = altura de referencia)."""
    cr.save()
    r = s * 0.30
    top = cy - s * 0.30          # centro del domo
    dome_r = s * 0.22
    skirt = s * 0.42             # semiancho de la falda
    lip_y = cy + s * 0.14        # borde inferior del cuerpo
    # cuerpo: domo + falda trapezoidal, relleno con degradado oro
    cr.new_sub_path()
    cr.arc(cx, top, dome_r, math.pi, 2 * math.pi)
    cr.move_to(cx - dome_r, top)
    cr.curve_to(cx - dome_r, top + s * 0.14, cx - skirt * 0.75, top + s * 0.20,
                cx - skirt, lip_y)
    cr.line_to(cx + skirt, lip_y)
    cr.curve_to(cx + skirt * 0.75, top + s * 0.20, cx + dome_r, top + s * 0.14,
                cx + dome_r, top)
    cr.close_path()
    g = cairo.RadialGradient(
        cx - dome_r * 0.5, top - dome_r * 0.5, dome_r * 0.2,
        cx, top + s * 0.1, skirt * 1.8,
    )
    g.add_color_stop_rgb(0.0, 0.88, 0.76, 0.40)
    g.add_color_stop_rgb(0.6, *GOLD)
    g.add_color_stop_rgb(1.0, *GOLD_DARK)
    cr.set_source(g)
    cr.fill()
    # labio inferior
    cr.set_line_width(max(1.4, s * 0.09))
    cr.set_source_rgb(*GOLD)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(cx - skirt, lip_y)
    cr.line_to(cx + skirt, lip_y)
    cr.stroke()
    # badajo
    cr.new_sub_path()
    cr.arc(cx, lip_y + s * 0.12, s * 0.06, 0, 2 * math.pi)
    cr.set_source_rgb(*GOLD_LIGHT)
    cr.fill()
    # asa
    cr.new_sub_path()
    cr.arc(cx, cy - s * 0.52, s * 0.09, 0, 2 * math.pi)
    cr.set_line_width(max(1.2, s * 0.09))
    cr.stroke()
    cr.restore()


def _draw_add_button(cr, cx, cy, r):
    """Boton '+ Anadir': aro dorado con cruz."""
    cr.save()
    cr.new_sub_path()
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    g = cairo.RadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.2, cx, cy, r)
    g.add_color_stop_rgb(0, 0.16, 0.15, 0.13)
    g.add_color_stop_rgb(1, 0.05, 0.045, 0.05)
    cr.set_source(g)
    cr.fill_preserve()
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(1.8)
    cr.stroke()
    cr.new_sub_path()
    cr.arc(cx, cy, r - 4, 0, 2 * math.pi)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(0.8)
    cr.stroke()
    arm = r * 0.42
    cr.set_source_rgb(*GOLD_LIGHT)
    cr.set_line_width(2.2)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(cx - arm, cy)
    cr.line_to(cx + arm, cy)
    cr.move_to(cx, cy - arm)
    cr.line_to(cx, cy + arm)
    cr.stroke()
    cr.restore()


def _draw_del_x(cr, cx, cy, r):
    """X pequena de borrar dentro de la fila."""
    s = r * 0.52
    cr.save()
    cr.set_source_rgb(0.75, 0.45, 0.28)
    cr.set_line_width(max(1.6, s * 0.34))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(cx - s, cy - s)
    cr.line_to(cx + s, cy + s)
    cr.move_to(cx + s, cy - s)
    cr.line_to(cx - s, cy + s)
    cr.stroke()
    cr.restore()


def _draw_padlock(cr, cx, cy, s):
    """Candado dorado (modo bloqueado), como los demas widgets."""
    cr.save()
    body_w = s * 1.5
    body_h = s * 1.2
    cr.new_sub_path()
    _rr(cr, cx - body_w, cy - body_h * 0.4, body_w * 2, body_h * 1.4, s * 0.25)
    cr.set_source_rgb(*GOLD)
    cr.fill()
    cr.new_sub_path()
    cr.arc(cx, cy - body_h * 0.45, s * 0.75, math.pi, 2 * math.pi)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(max(1.4, s * 0.32))
    cr.stroke()
    cr.new_sub_path()
    cr.arc(cx, cy + s * 0.15, s * 0.18, 0, 2 * math.pi)
    cr.set_source_rgb(0.02, 0.02, 0.03)
    cr.fill()
    cr.restore()


def draw_recordatorio(cr, w, h, rems, now, locked=False, flash_phase=0):
    """rems: lista ORDENADA [{note, target, created, fired}], mas nuevo al final.

    now: epoch del momento del render. flash_phase: ticks de 1 s de la
    animacion del destello (para que pulse la fila vencida).
    """
    if w <= 0 or h <= 0:
        return
    cr.set_operator(cairo.OPERATOR_OVER)

    geo = geometry(w, h)
    pad, x0, y0, ww, hh = geo["pad"], geo["x0"], geo["y0"], geo["ww"], geo["hh"]

    # --- sombra exterior
    cr.save()
    _rr(cr, x0, y0 + 4, ww, hh, 18)
    cr.set_source_rgba(0, 0, 0, 0.4)
    cr.fill()
    cr.restore()

    # --- cuerpo cuero
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

    # --- marco dorado doble
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

    # --- remaches
    cr.save()
    for cx, cy in ((x0 + 14, y0 + 14), (x0 + ww - 14, y0 + 14),
                   (x0 + 14, y0 + hh - 14), (x0 + ww - 14, y0 + hh - 14)):
        cr.new_sub_path()
        cr.arc(cx, cy, 3.2, 0, 2 * math.pi)
        cr.set_source_rgb(*GOLD)
        cr.fill()
        cr.new_sub_path()
        cr.arc(cx - 1, cy - 1, 1.1, 0, 2 * math.pi)
        cr.set_source_rgb(1, 0.95, 0.7)
        cr.fill()
    cr.restore()

    # --- header: campana + titulo
    title = i18n._("Reminders")
    title_size = max(9, min(ww * 0.072, 22))
    cr.save()
    cr.select_font_face("Serif", 0, 1)
    cr.set_font_size(title_size)
    tw = cr.text_extents(title).width
    cr.restore()
    tx = x0 + ww / 2 - tw / 2
    _text(cr, tx, geo["header_y"], title, title_size, GOLD_LIGHT, serif=True)
    _draw_bell(cr, tx - title_size * 0.85, geo["header_y"] - title_size * 0.32,
               title_size * 1.25)

    # --- filete bajo el titulo
    cr.save()
    ly = geo["dy"]
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1.0)
    cr.move_to(x0 + 18, ly)
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

    # --- filas
    rects = row_rects(w, h, len(rems))
    note_size = max(9, min(geo["row_h"] * 0.42, 15))
    right_size = note_size * 0.92
    pulse = 0.45 + 0.45 * max(0.0, math.sin(flash_phase * math.pi / 4.0))
    for i, (rx, ry, rw, rh) in enumerate(rects):
        rem = rems[i]
        expired = bool(rem.get("fired")) or rem.get("target", 0) <= now
        cy = ry + rh / 2
        cr.save()
        # fondo de fila
        _rr(cr, rx, ry, rw, rh, min(9, rh * 0.32))
        if expired:
            cr.set_source_rgba(*GOLD_LIGHT, 0.25 + pulse * 0.45)
            cr.fill_preserve()
            cr.set_source_rgb(*GOLD)
        else:
            g2 = cairo.RadialGradient(
                rx + rw * 0.3, ry + rh * 0.2, rh * 0.1,
                rx + rw / 2, ry + rh / 2, rw * 0.8,
            )
            g2.add_color_stop_rgb(0, 0.13, 0.135, 0.15)
            g2.add_color_stop_rgb(1, 0.035, 0.037, 0.045)
            cr.set_source(g2)
            cr.fill_preserve()
            cr.set_source_rgb(*GOLD_DARK)
        cr.set_line_width(1.2)
        cr.stroke()
        cr.restore()

        # anillo de progreso a la izquierda
        pr = rh * 0.26
        pcx, pcy = rx + rh * 0.42, cy
        span = max(60.0, float(rem.get("target", now)) - float(rem.get("created", now)))
        frac = max(0.0, min(1.0, (float(rem["target"]) - now) / span))
        cr.save()
        cr.new_sub_path()
        cr.arc(pcx, pcy, pr, 0, 2 * math.pi)
        cr.set_source_rgb(*LUME_DIM if not expired else GOLD_DARK)
        cr.set_line_width(2.0)
        cr.stroke()
        if frac > 0.002 and not expired:
            cr.new_sub_path()
            cr.arc(pcx, pcy, pr, -math.pi / 2, -math.pi / 2 + frac * 2 * math.pi)
            cr.set_source_rgb(*GOLD)
            cr.set_line_width(2.6)
            cr.stroke()
        cr.restore()

        # derecha primero (define el espacio que queda para la nota)
        t_left = rem["target"] - now
        if expired:
            right = i18n._("now!")
            r_bold = True
            color = (0.10, 0.09, 0.07)
        else:
            r_bold = True
            if t_left < 3 * 3600:
                right = i18n._("in {t}", t=format_countdown(t_left))
                color = RED if t_left < 60 else GOLD_LIGHT
            else:
                right = i18n._("at {t}", t=format_time_of_day(rem["target"]))
                color = GOLD_LIGHT
        right_x = rx + rw - rh * 0.52
        right_w = _text_width(cr, right, right_size, bold=r_bold)

        # nota (izquierda), recortada para no pisar la derecha ni la ✕
        note_x = pcx + pr + rh * 0.30
        note_max = max(18.0, right_x - right_w - 10.0 - note_x)
        shown = _truncate(cr, str(rem.get("note") or ""), note_max, note_size)
        if expired:
            _text(cr, note_x, cy + note_size * 0.35, shown,
                  note_size, (0.05, 0.05, 0.05), bold=True)
        else:
            _text(cr, note_x, cy + note_size * 0.35, shown, note_size, LUME)
        _text_right(cr, right_x, cy + right_size * 0.35, right,
                    right_size, color, bold=r_bold)

        # X de borrar
        _draw_del_x(cr, rx + rw - rh * 0.28, cy, rh * 0.17)

    # --- fila extra oculta: indicador
    if len(rems) > len(rects):
        extra = len(rems) - len(rects)
        _text(cr, x0 + ww * 0.5 - 8, geo["list_bottom"] - 4,
              i18n._("+{n} more", n=extra), max(8, note_size * 0.85), LUME_DIM)

    # --- footer + boton 'add'
    _draw_add_button(cr, *geo["add"])
    if not rems:
        empty = i18n._("No reminders")
        _text(cr, geo["add"][0] + geo["add"][2] * 2.2, geo["footer_y"],
              empty, max(9, note_size * 0.95), LUME_DIM)
    else:
        future = [rem["target"] for rem in rems if rem["target"] > now]
        if future:
            label = i18n._("next {t}", t=format_countdown(min(future) - now))
        else:
            label = i18n._("now!")
        _text(cr, geo["add"][0] + geo["add"][2] * 2.2, geo["footer_y"],
              label, max(9, note_size * 0.95), LUME_DIM)

    if locked:
        lx, ly2 = geo["lock"]
        _draw_padlock(cr, lx, ly2, 7.5)
