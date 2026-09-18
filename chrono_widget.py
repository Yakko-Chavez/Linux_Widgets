#!/usr/bin/env python3
"""Widget de escritorio Cronografo Mecanico para Wayland + GNOME.

Misma filosofia que Rolex/Agenda/Clima/Monitor/Sysmon:
- Ventana GTK4 transparente, sin decoracion, que no roba foco.
- Render offscreen con pycairo -> Gtk.Picture via Gdk.MemoryTexture.
- Arrastre Wayland, click derecho con menu, doble-click/L bloqueo.
- Esfera analogica (segundos centrales + subesferas min/horas/decimas) +
  ventana digital HH:MM:SS.D + pushers START/STOP y RESET como botones
  GTK reales sobre el dibujo (patron de la Agenda).
- Al cerrar se pierde la medicion (sin estado persistente).
"""

import os
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import widget_base as WB
from chrono_draw import chrono_button_zones, draw_chrono

APP_ID = "com.vibes.chrono-widget"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "chrono_config.json")
DEBUG = os.environ.get("CHRONO_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--debug"]

MIN_S, MAX_S = 100, 600
DEFAULT_S = 340

DEFAULT_CONFIG = {
    "size": DEFAULT_S,
    "locked": False,
    "opacity": 1.0,
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


def render_texture(size, elapsed_s, running, locked=False, scale=WB.SCALE):
    def paint(cr):
        draw_chrono(cr, size, size, elapsed_s, running, locked)

    return WB.render_texture(size, size, paint, scale=scale)


# Solo los pushers (el fondo transparente y el modo debug los genera la base).
CSS_BTN = """
window.chrono button.go {
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  box-shadow: none;
  outline: none;
  outline-width: 0;
  color: transparent;
  border-radius: 999px;
  padding: 0;
}
window.chrono button.go:hover {
  background-color: rgba(201,162,39,0.22);
  background-image: none;
  border-color: rgba(201,162,39,0.65);
}
window.chrono button.go:active {
  background-color: rgba(201,162,39,0.38);
  background-image: none;
}
window.chrono button.go:disabled {
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  box-shadow: none;
  outline: none;
}
"""


class ChronoWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,
            flags=WB.APP_FLAGS,
        )
        self.cfg = load_config()
        self.win = None
        self.image = None
        self.btn_start = None
        self.btn_reset = None
        self._timer_id = None
        # Estado del crono (se pierde al cerrar, por diseno).
        self._elapsed = 0.0
        self._t0 = None  # monotonic() al arrancar; None = parado

    # ---- estado ----
    def running(self):
        return self._t0 is not None

    def elapsed_now(self):
        if self._t0 is None:
            return self._elapsed
        return self._elapsed + (time.monotonic() - self._t0)

    def toggle(self):
        """START/STOP. Devuelve True si quedo corriendo."""
        if self._t0 is None:
            self._t0 = time.monotonic()
            started = True
        else:
            self._elapsed = self.elapsed_now()
            self._t0 = None
            started = False
        self._layout_buttons()
        self.refresh()
        return started

    def reset(self):
        """RESET. Solo en pausa (como un mecanico real). Devuelve True si reseteo."""
        if self._t0 is not None:
            return False
        self._elapsed = 0.0
        self._layout_buttons()
        self.refresh()
        return True

    def do_activate(self):
        print("[chrono] activate: creando ventana...", flush=True)
        if self.win:
            self.win.present()
            return

        size = int(self.cfg.get("size", DEFAULT_S))
        self.win = WB.make_window(
            self, "chrono",
            "Cronógrafo Mecánico" + (" [DEBUG]" if DEBUG else ""),
            size, size, self.cfg, DEBUG,
        )
        WB.install_css("chrono", DEBUG, extra=CSS_BTN)

        self.image = WB.make_picture(size, size)

        # Overlay con botones reales sobre los pushers dibujados.
        overlay = Gtk.Overlay()
        overlay.set_child(self.image)

        self.btn_start = self._make_go_button("Start / Stop (Espacio)")
        self.btn_start.connect("clicked", self._on_start_clicked)
        self.btn_start.set_halign(Gtk.Align.START)
        self.btn_start.set_valign(Gtk.Align.START)
        overlay.add_overlay(self.btn_start)

        self.btn_reset = self._make_go_button("Reset (R)")
        self.btn_reset.connect("clicked", self._on_reset_clicked)
        self.btn_reset.set_halign(Gtk.Align.START)
        self.btn_reset.set_valign(Gtk.Align.START)
        overlay.add_overlay(self.btn_reset)

        self.win.set_child(overlay)
        self._layout_buttons()

        drag = WB.wire_drag(self.image, self.win, lambda: self.cfg.get("locked"))
        drag.connect("drag-end", self.on_drag_end)

        WB.wire_click(self.image, 3, self.on_right_click)

        WB.wire_click(self.image, 1, self.on_left_click)

        WB.wire_keys(self.win, self.on_key)

        # Si el monitor es HiDPI (o cambia), re-render con el buffer correcto.
        self.win.connect("notify::scale-factor", lambda *_: self.refresh())

        self.win.present()
        print(f"[chrono] ventana presentada ({size}x{size}).", flush=True)
        self.refresh()
        self.restart_timer()

    # ---- render ----
    _frames_logged = 0

    def refresh(self):
        if self.image is None:
            return
        size = int(self.cfg.get("size", DEFAULT_S))
        locked = bool(self.cfg.get("locked", False))
        scale = WB.widget_scale(self.win)
        try:
            tex = render_texture(size, self.elapsed_now(), self.running(),
                                 locked, scale=scale)
            self.image.set_paintable(tex)
            self.image.set_size_request(size, size)
            if ChronoWidget._frames_logged < 5:
                ChronoWidget._frames_logged += 1
                iw, ih = tex.get_intrinsic_width(), tex.get_intrinsic_height()
                ww, wh = self.win.get_width(), self.win.get_height()
                print(f"[chrono] diagnostico: size={size} escala=x{scale} "
                      f"buffer={iw}x{ih} ventana={ww}x{wh}", flush=True)
        except Exception as e:
            print(f"[chrono] ERROR render: {e}", file=sys.stderr, flush=True)

    def restart_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        # 50 ms: barrido suave + decimas fluidas.
        self._timer_id = GLib.timeout_add(50, self.on_tick)

    def on_tick(self):
        self.refresh()
        return True

    # ---- botones overlay ----
    @staticmethod
    def _make_go_button(tooltip):
        b = Gtk.Button(label="")
        b.add_css_class("flat")
        b.add_css_class("go")
        b.set_tooltip_text(tooltip)
        b.set_focusable(False)
        b.set_focus_on_click(False)
        try:
            b.set_cursor_from_name("pointer")
        except Exception:
            pass
        return b

    def _layout_buttons(self):
        """Posiciona los botones transparentes sobre los pushers Cairo."""
        if self.btn_start is None:
            return
        size = int(self.cfg.get("size", DEFAULT_S))
        zones = chrono_button_zones(size, size)
        locked = bool(self.cfg.get("locked", False))
        for btn, name in ((self.btn_start, "start"),
                          (self.btn_reset, "reset")):
            cx, cy, r = zones[name]
            side = int(r * 2)
            btn.set_size_request(side, side)
            # Overlay con halign START: margenes absolutos desde la esquina.
            btn.set_margin_start(int(cx - r))
            btn.set_margin_top(int(cy - r))
            btn.set_margin_end(0)
            btn.set_margin_bottom(0)
        self.btn_start.set_sensitive(not locked)
        # Reset mecanico: solo en pausa (y nunca bloqueado).
        self.btn_reset.set_sensitive(not locked and not self.running())

    def _on_start_clicked(self, _btn):
        if not self.cfg.get("locked"):
            started = self.toggle()
            print(f"[chrono] {'marcha' if started else 'paro'} "
                  f"({self.elapsed_now():.1f}s)", flush=True)

    def _on_reset_clicked(self, _btn):
        if not self.cfg.get("locked"):
            if self.reset():
                print("[chrono] reset a cero", flush=True)

    # ---- interaccion ----
    def _save_position(self):
        """Guarda la posicion actual de la ventana en config (best-effort)."""
        WB.store_position(self.win, self.cfg, CONFIG_PATH)

    def on_drag_end(self, gesture, _offset_x, _offset_y):
        """Guardar posicion despues de arrastrar."""
        self._save_position()

    def on_left_click(self, gesture, n_press, x, y):
        if n_press == 2:
            WB.toggle_locked(self.cfg, CONFIG_PATH)
            self._layout_buttons()
            self.refresh()

    def on_right_click(self, gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        WB.popup_menu(self.image, x, y, self, [
            ("Pausar" if self.running() else "Iniciar", "go", self.act_go),
            ("Reset", "reset", self.act_reset),
            ("Bloquear clicks ✓" if self.cfg.get("locked") else "Bloquear clicks",
             "lock", self.act_lock),
            ("Tamaño +", "bigger", self.act_bigger),
            ("Tamaño −", "smaller", self.act_smaller),
            ("Salir", "quit", self.act_quit),
        ])

    def on_key(self, _ctl, keyval, _keycode, _state):
        name = Gdk.keyval_name(keyval) or ""
        nl = name.lower()
        if WB.is_quit_key(name, nl):
            self.quit()
            return True
        if WB.is_lock_key(nl):
            WB.toggle_locked(self.cfg, CONFIG_PATH)
            self._layout_buttons()
            self.refresh()
            print(f"[chrono] {'bloqueado' if self.cfg.get('locked') else 'desbloqueado'}", flush=True)
            return True
        if nl == "space":
            if not self.cfg.get("locked"):
                self.toggle()
            return True
        if nl == "r":
            if not self.cfg.get("locked"):
                self.reset()
            return True
        if WB.is_bigger_key(name):
            self.resize_by(40)
            return True
        if WB.is_smaller_key(name):
            self.resize_by(-40)
            return True
        return False

    # ---- acciones ----
    def act_go(self, *_):
        self.toggle()

    def act_reset(self, *_):
        self.reset()

    def act_lock(self, *_):
        WB.toggle_locked(self.cfg, CONFIG_PATH)
        self._layout_buttons()
        self.refresh()

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

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
    app = ChronoWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
