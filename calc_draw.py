"""Dibujo vectorial Calculadora Dorada (cientifica) con Cairo.

100% procedural, sin imagenes externas. Caja cuadrada de bordes
redondeados a juego con la Agenda de Lujo y el Clima Dorado (mismos
filetes y remaches) y pantalla oscura con digitos LUME como la ventana
digital del Cronografo Mecanico.

Parrilla 6x7: fila de memoria + limpiar, dos filas cientificas
(trig/logs/DEG, potencias/raices/constantes) y bloque aritmetico con
"=" alto (2 filas) y "0" de ancho completo.

Funciones:
  draw_calc(cr, w, h, display, sub_display, has_memory, locked, angle_mode)
  calc_button_zones(w, h) -> {key_id: (x, y, w, h)} en coords logicas
  KEY_LABELS: id de tecla -> etiqueta por defecto
"""

import math

GOLD = (0.79, 0.64, 0.15)
GOLD_LIGHT = (0.93, 0.82, 0.45)
GOLD_DARK = (0.48, 0.37, 0.10)
CREAM = (0.92, 0.89, 0.80)
LUME = (0.93, 0.95, 0.88)
MUTED = (0.55, 0.52, 0.45)
RED = (0.85, 0.25, 0.20)

PAD = 6  # margen de la caja (igual que clima_draw)

# "Sans" generico resuelve a Noto Sans en GNOME, que NO trae U+2212 (−) ni
# U+232B (⌫): se pide DejaVu Sans explicito para teclas y display.
FONT = "DejaVu Sans"

# Teclado 6x7: (id, etiqueta, colspan, rowspan). None = celda ocupada por
# la tecla "=" alta de la fila anterior; el "0" ocupa toda la fila final.
KEY_GRID = (
    (("mc", "MC", 1, 1), ("mr", "MR", 1, 1), ("m_minus", "M−", 1, 1),
     ("m_plus", "M+", 1, 1), ("clear", "C", 1, 1), ("back", "⌫", 1, 1)),
    (("sin", "sin", 1, 1), ("cos", "cos", 1, 1), ("tan", "tan", 1, 1),
     ("ln", "ln", 1, 1), ("log", "log", 1, 1), ("deg", "DEG", 1, 1)),
    (("sqrt", "√", 1, 1), ("sqr", "x²", 1, 1), ("pow", "xʸ", 1, 1),
     ("inv", "1/x", 1, 1), ("pi", "π", 1, 1), ("e_num", "e", 1, 1)),
    (("7", "7", 1, 1), ("8", "8", 1, 1), ("9", "9", 1, 1),
     ("div", "÷", 1, 1), ("pct", "%", 1, 1), ("neg", "±", 1, 1)),
    (("4", "4", 1, 1), ("5", "5", 1, 1), ("6", "6", 1, 1),
     ("mul", "×", 1, 1), ("minus", "−", 1, 1), ("eq", "=", 1, 2)),
    (("1", "1", 1, 1), ("2", "2", 1, 1), ("3", "3", 1, 1),
     ("plus", "+", 1, 1), ("dot", ".", 1, 1), None),
    (("zero", "0", 6, 1),),
)

KEY_LABELS = {kid: label for row in KEY_GRID
              for cell in row if cell
              for (kid, label, _cs, _rs) in (cell,)}

OPERATORS = frozenset(("div", "mul", "minus", "plus", "eq", "pow"))
MEMORY_KEYS = frozenset(("mc", "mr", "m_minus", "m_plus"))
SCI_KEYS = frozenset(("sin", "cos", "tan", "ln", "log", "deg", "sqrt",
                      "sqr", "pow", "inv", "pi", "e_num"))

ROWS, COLS = 7, 6


def _keypad_geometry(size):
    """Origen de la parrilla, celda y gap (coords logicas)."""
    x0, y0 = size * 0.06, size * 0.305
    x1, y1 = size * 0.94, size * 0.968
    gap = max(2.0, size * 0.014)
    cw = (x1 - x0 - gap * (COLS - 1)) / COLS
    ch = (y1 - y0 - gap * (ROWS - 1)) / ROWS
    return x0, y0, cw, ch, gap


def _rr(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _text_centered(cr, cx, y, text, size, color, serif=False, bold=True):
    cr.save()
    cr.select_font_face("Serif" if serif else FONT, 0, 1 if bold else 0)
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(cx - ext.width / 2 - ext.x_bearing, y)
    cr.show_text(text)
    cr.restore()


def _text_right(cr, x_right, y, text, size, color, bold=True):
    cr.save()
    cr.select_font_face(FONT, 0, 1 if bold else 0)
    cr.set_font_size(size)
    cr.set_source_rgb(*color)
    ext = cr.text_extents(text)
    cr.move_to(x_right - ext.width - ext.x_bearing, y)
    cr.show_text(text)
    cr.restore()


def calc_button_zones(w, h):
    """Rects logicos de cada tecla, para posicionar los Gtk.Button overlay.

    La zona crece medio gap por lado: el hueco entre teclas sigue siendo
    clickeable, como en una calculadora fisica.
    """
    size = min(w, h)
    if size <= 0:
        return {}
    x0, y0, cw, ch, gap = _keypad_geometry(size)
    zones = {}
    for r, row in enumerate(KEY_GRID):
        c = 0
        for cell in row:
            if cell is None:
                c += 1
                continue
            kid, _label, cspan, rspan = cell
            x = x0 + c * (cw + gap)
            y = y0 + r * (ch + gap)
            zw = cw * cspan + gap * (cspan - 1)
            zh = ch * rspan + gap * (rspan - 1)
            zones[kid] = (x - gap / 2, y - gap / 2, zw + gap, zh + gap)
            c += cspan
    return zones


def _draw_key(cr, kid, label, x, y, w, h):
    r = min(9.0, h * 0.28)
    # sombra inferior sutil (tecla con volumen)
    _rr(cr, x, y + h * 0.06, w, h, r)
    cr.set_source_rgba(0, 0, 0, 0.45)
    cr.fill()
    _rr(cr, x, y, w, h, r)
    cr.set_source_rgb(0.115, 0.115, 0.125)
    cr.fill()
    if kid == "clear":
        border, label_color, line_w = RED, CREAM, 1.5
    elif kid in OPERATORS:
        border, label_color, line_w = GOLD, GOLD_LIGHT, 1.4
    elif kid in MEMORY_KEYS:
        border, label_color, line_w = GOLD_DARK, MUTED, 1.0
    elif kid in SCI_KEYS:
        border, label_color, line_w = GOLD_DARK, CREAM, 1.0
    else:
        border, label_color, line_w = GOLD_DARK, LUME, 1.0
    _rr(cr, x, y, w, h, r)
    cr.set_source_rgb(*border)
    cr.set_line_width(line_w)
    cr.stroke()
    if kid == "eq":
        # tecla de accion alta: capote dorado solido y texto oscuro
        _rr(cr, x + 2, y + 2, w - 4, h - 4, max(2.0, r - 2))
        cr.set_source_rgb(*GOLD)
        cr.fill()
        label_color = (0.08, 0.065, 0.02)
    if kid in MEMORY_KEYS or kid in SCI_KEYS:
        fsize = h * 0.32
    elif kid == "eq":
        fsize = h * 0.42
    else:
        fsize = h * 0.44
    _text_centered(cr, x + w / 2, y + h * 0.5 + fsize * 0.36, label, fsize,
                   label_color)


def draw_calc(cr, w, h, display="0", sub_display="", has_memory=False,
              locked=False, angle_mode="DEG"):
    import cairo

    size = min(w, h)
    if size <= 0:
        return
    cr.set_operator(cairo.OPERATOR_OVER)

    # --- Caja cuadrada redondeada (patron Clima Dorado) ---
    cr.save()
    _rr(cr, PAD, PAD, w - PAD * 2, h - PAD * 2, 18)
    g = cairo.RadialGradient(w / 2, h * 0.2, 10, w / 2, h / 2, h * 0.7)
    g.add_color_stop_rgb(0, 0.09, 0.09, 0.10)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.025)
    cr.set_source(g)
    cr.fill()
    _rr(cr, PAD, PAD, w - PAD * 2, h - PAD * 2, 18)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(2.2)
    cr.stroke()
    _rr(cr, PAD + 6, PAD + 6, w - (PAD + 6) * 2, h - (PAD + 6) * 2, 14)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1.1)
    cr.stroke()
    for rx, ry in [(PAD + 9, PAD + 9), (w - PAD - 9, PAD + 9),
                   (PAD + 9, h - PAD - 9), (w - PAD - 9, h - PAD - 9)]:
        cr.new_sub_path()
        cr.arc(rx, ry, 3.4, 0, 2 * math.pi)
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.fill()
    cr.restore()

    # --- Cabecera ---
    header_y = max(22, h * 0.058)
    header_size = max(9, min(19, h * 0.038))
    _text_centered(cr, w / 2, header_y, "CALCULADORA", header_size,
                   GOLD_LIGHT, serif=True)
    line_y = header_y + max(6, h * 0.020)
    cr.save()
    cr.move_to(max(16, w * 0.08), line_y)
    cr.line_to(w - max(16, w * 0.08), line_y)
    cr.set_source_rgb(*GOLD_DARK)
    cr.set_line_width(1)
    cr.stroke()
    cr.restore()

    # --- Pantalla ---
    dw, dh = w * 0.86, h * 0.135
    dx, dy = (w - dw) / 2, line_y + max(7, h * 0.018)
    _rr(cr, dx, dy, dw, dh, dh * 0.22)
    cr.set_source_rgb(0.02, 0.025, 0.03)
    cr.fill()
    _rr(cr, dx, dy, dw, dh, dh * 0.22)
    cr.set_source_rgb(*GOLD)
    cr.set_line_width(1.2)
    cr.stroke()
    # sub-linea: M (memoria) y DEG/RAD a la izquierda, operacion a la derecha
    sub_y = dy + dh * 0.36
    sub_size = max(7, dh * 0.26)
    cr.save()
    cr.select_font_face(FONT, 0, 1)
    cr.set_font_size(sub_size)
    if has_memory:
        cr.set_source_rgb(*GOLD_LIGHT)
        cr.move_to(dx + dw * 0.035, sub_y)
        cr.show_text("M")
    if angle_mode == "RAD":
        cr.set_source_rgb(*MUTED)
        cr.move_to(dx + dw * (0.10 if has_memory else 0.035), sub_y)
        cr.show_text("RAD")
    cr.restore()
    if sub_display:
        _text_right(cr, dx + dw * 0.965, sub_y, sub_display, sub_size, MUTED,
                    bold=False)
    # display principal, alineado a la derecha y con auto-ajuste de fuente
    cr.save()
    cr.select_font_face(FONT, 0, 1)
    main_size = dh * 0.52
    avail = dw * 0.90
    while main_size > 6:
        cr.set_font_size(main_size)
        if cr.text_extents(display).width <= avail:
            break
        main_size *= 0.88
    cr.set_font_size(main_size)
    cr.set_source_rgb(*LUME)
    ext = cr.text_extents(display)
    cr.move_to(dx + dw * 0.965 - ext.width - ext.x_bearing, dy + dh * 0.84)
    cr.show_text(display)
    cr.restore()

    # --- Teclas ---
    x0, y0, cw, ch, _gap = _keypad_geometry(size)
    for r, row in enumerate(KEY_GRID):
        c = 0
        for cell in row:
            if cell is None:
                c += 1
                continue
            kid, label, cspan, rspan = cell
            x = x0 + c * (cw + _gap)
            y = y0 + r * (ch + _gap)
            kw = cw * cspan + _gap * (cspan - 1)
            kh = ch * rspan + _gap * (rspan - 1)
            if kid == "deg":
                label = angle_mode  # la tecla siempre muestra el modo actual
            _draw_key(cr, kid, label, x, y, kw, kh)
            c += cspan

    # --- Candadito si bloqueado (esquina superior derecha) ---
    if locked:
        cr.save()
        lx, ly = w - 28, h * 0.050
        cr.set_source_rgb(*GOLD)
        cr.set_line_width(2.0)
        cr.set_line_cap(1)
        cr.new_sub_path()
        cr.arc(lx, ly - 2, 6, math.pi, 2 * math.pi)
        cr.stroke()
        _rr(cr, lx - 9, ly - 2, 18, 13, 3)
        cr.stroke()
        cr.new_sub_path()
        cr.arc(lx, ly + 2.5, 1.8, 0, 2 * math.pi)
        cr.fill()
        cr.restore()
