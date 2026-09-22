#!/usr/bin/env python3
"""Widget de escritorio Calculadora Dorada para Wayland + GNOME.

Misma filosofia que Reloj/Agenda/Clima/Monitor/Chrono:
- Ventana GTK4 transparente, sin decoracion, que no roba foco.
- Render offscreen con pycairo -> Gtk.Picture via Gdk.MemoryTexture.
- Arrastre Wayland, click derecho con menu, doble-click/L bloqueo.
- Teclado 6x7 dibujado en vectorial con botones GTK reales encima
  (patron de los pushers del Cronografo).
- Motor cientifico con memoria (M+/M-/MR/MC): trigonometricas con modo
  DEG/RAD, ln/log, raiz, cuadrado, x^y, 1/x y constantes pi/e.

Teclas fisicas: 0-9 . + - * / = Enter Backspace, c/Delete = C, m = MR.
"""

import math
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

import widget_base as WB
from calc_draw import KEY_LABELS, calc_button_zones, draw_calc

APP_ID = "com.vibes.calc-widget"
CONFIG_PATH = WB.config_path("calc_config.json")
DEBUG = os.environ.get("CALC_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--debug"]

MIN_S, MAX_S = 300, 700
DEFAULT_S = 440

DEFAULT_CONFIG = {
    "size": DEFAULT_S,
    "locked": False,
    "opacity": 1.0,
    "angle": "DEG",
    "x": -1,
    "y": -1,
}


def load_config():
    return WB.load_config(
        CONFIG_PATH, DEFAULT_CONFIG,
        int_ranges={"size": (MIN_S, MAX_S, DEFAULT_S)},
        float_ranges={"opacity": (0.1, 1.0, 1.0)},
    )


def save_config(cfg):
    WB.save_config(CONFIG_PATH, cfg)


def format_number(x):
    """Numero a texto recortado: sin ceros finales, sin artefactos float."""
    x = float(x)
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    if len(s) > 14:
        s = f"{x:.6g}"
    return s


def _is_bad(x):
    return x is None or x != x or x in (float("inf"), float("-inf"))


class CalcEngine:
    """Motor de calculo cientifico con memoria. Sin nada de GTK."""

    def __init__(self):
        self.entry = "0"
        self.acc = None
        self.op = None
        self.memory = 0.0
        self.fresh = True   # el proximo digito reemplaza el display
        self.error = False
        self.angle_mode = "DEG"  # "DEG" | "RAD"

    # ---- internos ----
    @staticmethod
    def _to_num(s):
        try:
            return float(s)
        except (TypeError, ValueError):
            return 0.0

    def _compute(self, a, b, op):
        try:
            if op == "+":
                return a + b
            if op == "−":
                return a - b
            if op == "×":
                return a * b
            if op == "^":
                if a == 0 and b < 0:
                    return None
                r = a ** b  # base negativa con exp fraccionario -> complex
                return None if isinstance(r, complex) else r
            if b == 0:
                return None  # ÷0 -> Error
            return a / b
        except (OverflowError, ValueError, ZeroDivisionError):
            return None

    def _set_error(self):
        self.error = True
        self.entry = "Error"
        self.acc = None
        self.op = None
        self.fresh = True

    def _unary_result(self, r):
        """Resultado de una funcion unaria sobre el display."""
        if _is_bad(r):
            self._set_error()
            return
        if abs(r) < 1e-10:
            r = 0.0  # sin(pi) en RAD: evita "-0" por el redondeo de pi
        self.entry = format_number(r)
        self.fresh = True

    def _angle(self, x):
        return math.radians(x) if self.angle_mode == "DEG" else x

    # ---- teclas ----
    def digit(self, d):
        if self.error:
            self.clear()
        if self.fresh:
            self.entry = "0." if d == "." else d
            self.fresh = False
            return
        if d == ".":
            if "." not in self.entry:
                self.entry += "."
            return
        if self.entry == "0":
            self.entry = d
        elif len(self.entry) < 15:
            self.entry += d

    def set_op(self, op):
        if self.error:
            self.clear()
        cur = self._to_num(self.entry)
        if self.op is not None and not self.fresh:
            r = self._compute(self.acc, cur, self.op)
            if _is_bad(r):
                self._set_error()
                return
            self.entry = format_number(r)
            self.acc = r
        else:
            self.acc = cur
        self.op = op
        self.fresh = True

    def equals(self):
        if self.error or self.op is None:
            self.fresh = True
            return
        cur = self._to_num(self.entry)
        r = self._compute(self.acc, cur, self.op)
        if _is_bad(r):
            self._set_error()
            return
        self.entry = format_number(r)
        self.acc = None
        self.op = None
        self.fresh = True

    def clear(self):
        self.entry = "0"
        self.acc = None
        self.op = None
        self.fresh = True
        self.error = False

    def backspace(self):
        if self.error:
            self.clear()
            return
        if self.fresh:
            return
        self.entry = self.entry[:-1]
        if self.entry in ("", "-"):
            self.entry = "0"

    def neg(self):
        if self.error:
            return
        if self.entry.startswith("-"):
            self.entry = self.entry[1:]
        elif self.entry != "0":
            self.entry = "-" + self.entry

    def pct(self):
        if self.error:
            return
        self.entry = format_number(self._to_num(self.entry) / 100.0)
        self.fresh = True

    # ---- cientificas (unarias sobre el display) ----
    def sin(self):
        if self.error:
            self.clear()
        self._unary_result(math.sin(self._angle(self._to_num(self.entry))))

    def cos(self):
        if self.error:
            self.clear()
        self._unary_result(math.cos(self._angle(self._to_num(self.entry))))

    def tan(self):
        if self.error:
            self.clear()
        x = self._to_num(self.entry)
        if self.angle_mode == "DEG" and x % 180 == 90:
            self._set_error()  # tan(90°) no existe
            return
        self._unary_result(math.tan(self._angle(x)))

    def sqrt(self):
        if self.error:
            self.clear()
        x = self._to_num(self.entry)
        self._unary_result(None if x < 0 else math.sqrt(x))

    def sqr(self):
        if self.error:
            self.clear()
        self._unary_result(self._to_num(self.entry) ** 2)

    def inv(self):
        if self.error:
            self.clear()
        x = self._to_num(self.entry)
        self._unary_result(None if x == 0 else 1.0 / x)

    def ln(self):
        if self.error:
            self.clear()
        try:
            r = math.log(self._to_num(self.entry))
        except (ValueError, OverflowError):
            r = None
        self._unary_result(r)

    def log(self):
        if self.error:
            self.clear()
        try:
            r = math.log10(self._to_num(self.entry))
        except (ValueError, OverflowError):
            r = None
        self._unary_result(r)

    def const_pi(self):
        self._enter_constant(math.pi)

    def const_e(self):
        self._enter_constant(math.e)

    def _enter_constant(self, v):
        """Entra pi/e como display: si habia operador pendiente, sigue vivo."""
        if self.error:
            self.clear()
        self.entry = format_number(v)
        self.fresh = True

    def toggle_angle(self):
        self.angle_mode = "RAD" if self.angle_mode == "DEG" else "DEG"

    # ---- memoria ----
    def m_plus(self):
        self.memory += self._to_num(self.entry)

    def m_minus(self):
        self.memory -= self._to_num(self.entry)

    def m_recall(self):
        if self.error:
            self.clear()
        self.entry = format_number(self.memory)
        self.fresh = False

    def m_clear(self):
        self.memory = 0.0

    @property
    def has_memory(self):
        return self.memory != 0.0

    def sub_text(self):
        """Linea pequenia de la pantalla: operacion pendiente."""
        if self.error or self.op is None or self.acc is None:
            return ""
        return f"{format_number(self.acc)} {self.op}"


# Solo las teclas (el fondo transparente y el modo debug los genera la base).
CSS_KEY = """
window.calc button.key {
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  box-shadow: none;
  outline: none;
  outline-width: 0;
  color: transparent;
  border-radius: 12px;
  padding: 0;
}
window.calc button.key:hover {
  background-color: rgba(201,162,39,0.20);
  background-image: none;
  border-color: rgba(201,162,39,0.55);
}
window.calc button.key:active {
  background-color: rgba(201,162,39,0.38);
  background-image: none;
}
"""

# Tecla fisica -> id de tecla del teclado dibujado.
KEYVAL_MAP = {
    ".": "dot", "comma": "dot", "KP_Decimal": "dot",
    "plus": "plus", "KP_Add": "plus",
    "minus": "minus", "KP_Subtract": "minus",
    "asterisk": "mul", "KP_Multiply": "mul",
    "slash": "div", "KP_Divide": "div",
    "equal": "eq", "Return": "eq", "KP_Enter": "eq",
    "BackSpace": "back",
    "Delete": "clear", "percent": "pct",
}


class CalcWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,
            flags=WB.APP_FLAGS,
        )
        self.cfg = load_config()
        self.calc = CalcEngine()
        angle = str(self.cfg.get("angle", "DEG")).upper()
        self.calc.angle_mode = "RAD" if angle == "RAD" else "DEG"
        self.win = None
        self.image = None
        self.buttons = {}  # key_id -> Gtk.Button

    def do_activate(self):
        print("[calc] activate: creando ventana...", flush=True)
        if self.win:
            self.win.present()
            return

        size = int(self.cfg.get("size", DEFAULT_S))
        self.win = WB.make_window(
            self, "calc",
            "Calculadora Dorada" + (" [DEBUG]" if DEBUG else ""),
            size, size, self.cfg, DEBUG,
        )
        WB.install_css("calc", DEBUG, extra=CSS_KEY)

        self.image = WB.make_picture(size, size)
        overlay = Gtk.Overlay()
        overlay.set_child(self.image)
        self._build_buttons(overlay)
        self.win.set_child(overlay)

        drag = WB.wire_drag(self.image, self.win, lambda: self.cfg.get("locked"))
        drag.connect("drag-end", self.on_drag_end)

        WB.wire_click(self.image, 3, self.on_right_click)
        WB.wire_click(self.image, 1, self.on_left_click)
        WB.wire_keys(self.win, self.on_key)

        # Si el monitor es HiDPI (o cambia), re-render con el buffer correcto.
        self.win.connect("notify::scale-factor", lambda *_: self.refresh())

        self.win.present()
        print(f"[calc] ventana presentada ({size}x{size}).", flush=True)
        self.refresh()

    # ---- botones overlay ----
    def _build_buttons(self, overlay):
        for kid in KEY_LABELS:
            btn = Gtk.Button(label=KEY_LABELS[kid])
            btn.add_css_class("key")
            btn.set_focusable(False)
            btn.set_focus_on_click(False)
            btn.set_halign(Gtk.Align.START)
            btn.set_valign(Gtk.Align.START)
            btn.connect("clicked", self._on_key_clicked, kid)
            overlay.add_overlay(btn)
            self.buttons[kid] = btn
        self._layout_buttons()

    def _layout_buttons(self):
        """Posiciona los botones sobre las teclas dibujadas (coords logicas)."""
        if self.win is None:
            return
        size = int(self.cfg.get("size", DEFAULT_S))
        for kid, (x, y, zw, zh) in calc_button_zones(size, size).items():
            btn = self.buttons[kid]
            btn.set_size_request(int(zw), int(zh))
            # halign/valign START: margenes absolutos desde la esquina.
            btn.set_margin_start(int(x))
            btn.set_margin_top(int(y))
            btn.set_margin_end(0)
            btn.set_margin_bottom(0)
        locked = bool(self.cfg.get("locked", False))
        for btn in self.buttons.values():
            btn.set_sensitive(not locked)

    def _on_key_clicked(self, _btn, kid):
        if not self.cfg.get("locked"):
            self.press(kid)

    def press(self, kid):
        c = self.calc
        if kid in "0123456789":
            c.digit(kid)
        elif kid == "dot":
            c.digit(".")
        elif kid == "plus":
            c.set_op("+")
        elif kid == "minus":
            c.set_op("−")
        elif kid == "mul":
            c.set_op("×")
        elif kid == "div":
            c.set_op("÷")
        elif kid == "eq":
            c.equals()
        elif kid == "clear":
            c.clear()
        elif kid == "back":
            c.backspace()
        elif kid == "neg":
            c.neg()
        elif kid == "pct":
            c.pct()
        elif kid == "sin":
            c.sin()
        elif kid == "cos":
            c.cos()
        elif kid == "tan":
            c.tan()
        elif kid == "sqrt":
            c.sqrt()
        elif kid == "sqr":
            c.sqr()
        elif kid == "pow":
            c.set_op("^")
        elif kid == "inv":
            c.inv()
        elif kid == "ln":
            c.ln()
        elif kid == "log":
            c.log()
        elif kid == "pi":
            c.const_pi()
        elif kid == "e_num":
            c.const_e()
        elif kid == "deg":
            c.toggle_angle()
            self.cfg["angle"] = c.angle_mode
            save_config(self.cfg)
        elif kid == "mc":
            c.m_clear()
        elif kid == "mr":
            c.m_recall()
        elif kid == "m_plus":
            c.m_plus()
        elif kid == "m_minus":
            c.m_minus()
        self.refresh()

    # ---- render ----
    def refresh(self):
        if self.image is None:
            return
        size = int(self.cfg.get("size", DEFAULT_S))
        locked = bool(self.cfg.get("locked", False))
        scale = WB.widget_scale(self.win)

        def paint(cr):
            draw_calc(cr, size, size, self.calc.entry, self.calc.sub_text(),
                      self.calc.has_memory, locked, self.calc.angle_mode)

        try:
            tex = WB.render_texture(size, size, paint, scale=scale)
            self.image.set_paintable(tex)
            self.image.set_size_request(size, size)
        except Exception as e:
            print(f"[calc] ERROR render: {e}", file=sys.stderr, flush=True)

    # ---- interaccion ----
    def _save_position(self):
        """Guarda la posicion actual de la ventana en config (best-effort)."""
        WB.store_position(self.win, self.cfg, CONFIG_PATH)

    def on_drag_end(self, _gesture, _offset_x, _offset_y):
        self._save_position()

    def on_left_click(self, _gesture, n_press, _x, _y):
        if n_press == 2:
            self._toggle_lock()

    def on_right_click(self, _gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        WB.popup_menu(self.image, x, y, self, [
            ("Lock clicks ✓" if self.cfg.get("locked") else "Lock clicks",
             "lock", self.act_lock),
            ("Size +", "bigger", self.act_bigger),
            ("Size −", "smaller", self.act_smaller),
            ("Settings…", "settings", self.act_settings),
            ("Quit", "quit", self.act_quit),
        ])

    def _toggle_lock(self):
        WB.toggle_locked(self.cfg, CONFIG_PATH)
        self._layout_buttons()
        self.refresh()
        print(f"[calc] {'bloqueado' if self.cfg.get('locked') else 'desbloqueado'}",
              flush=True)

    def on_key(self, _ctl, keyval, _keycode, _state):
        # A diferencia del resto de la coleccion, +/-/= NO redimensionan:
        # son operadores. El tamaño va por menu o Settings.
        name = Gdk.keyval_name(keyval) or ""
        nl = name.lower()
        if WB.is_quit_key(name, nl):
            self.quit()
            return True
        if WB.is_lock_key(nl):
            self._toggle_lock()
            return True
        if self.cfg.get("locked"):
            return True
        if name.isdigit():
            self.press(name)
            return True
        if name.startswith("KP_") and name[3:].isdigit():
            self.press(name[3:])
            return True
        if nl == "c":
            self.press("clear")
            return True
        if nl == "m":
            self.press("mr")
            return True
        kid = KEYVAL_MAP.get(name)
        if kid:
            self.press(kid)
            return True
        return False

    # ---- acciones ----
    def act_lock(self, *_):
        self._toggle_lock()

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

    def act_settings(self, *_):
        WB.settings_dialog(self.win, self.cfg, [
            ("size", "Size", "spin", (MIN_S, MAX_S, 10, 0)),
            ("opacity", "Opacity", "spin", (0.1, 1.0, 0.05, 2)),
        ], self.apply_settings)

    def apply_settings(self, cfg):
        save_config(cfg)
        try:
            self.win.set_opacity(float(cfg.get("opacity", 1.0)))
        except (TypeError, ValueError):
            pass
        size = int(cfg.get("size", DEFAULT_S))
        self.win.set_default_size(size, size)
        self._layout_buttons()
        self.refresh()

    def act_quit(self, *_):
        self.quit()

    def resize_by(self, delta):
        size = max(MIN_S, min(MAX_S, int(self.cfg.get("size", DEFAULT_S)) + delta))
        self.cfg["size"] = size
        save_config(self.cfg)
        self.win.set_default_size(size, size)
        self.refresh()
        self._layout_buttons()
        self._save_position()


def main():
    app = CalcWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
