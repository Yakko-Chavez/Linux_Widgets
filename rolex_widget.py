#!/usr/bin/env python3
"""Widget de escritorio Rolex Submariner para Wayland + GNOME.

Ventana GTK4 transparente, sin decoracion, solo visual.
- Render offscreen con pycairo -> Gtk.Image (NO necesita python3-gi-cairo,
  que falta en Ubuntu base y requiere sudo para instalar).
- Movimiento sweep suave o tick segun config.
- Arrastre con Super+drag de GNOME o gesto (Wayland: el compositor decide posicion).
- Click derecho: menu. Doble click / L: bloquear.
"""

import os
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import widget_base as WB
from rolex_draw import draw_rolex

APP_ID = "com.vibes.rolex-widget"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEBUG = os.environ.get("ROLEX_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:  # Gtk no conoce este flag, quitarlo antes de app.run
    sys.argv = [a for a in sys.argv if a != "--debug"]

DEFAULT_CONFIG = {
    "size": 340,
    "sweep": True,
    "locked": False,
    "opacity": 1.0,
    "x": -1,
    "y": -1,
}


def load_config():
    return WB.load_config(
        CONFIG_PATH, DEFAULT_CONFIG,
        int_ranges={"size": (100, 600, 340)},
        float_ranges={"opacity": (0.1, 1.0, 1.0)},
    )


def save_config(cfg):
    WB.save_config(CONFIG_PATH, cfg)


def render_texture(size, scale=WB.SCALE):
    """Renderiza el reloj a Gdk.Texture 100% en memoria.

    Sin archivos, sin GdkPixbuf, sin puente cairo de PyGObject:
    el layout en memoria de cairo ARGB32 (little-endian) coincide con
    GDK_MEMORY_B8G8R8A8_PREMULTIPLIED. Elimina de raiz la ventana
    transparente (carreras PNG + cache de Gtk.Image).

    scale debe ser widget_scale(win): el buffer va a tamano x escala para
    que la ventana mida `size` en cualquier monitor (x1 o HiDPI).
    """
    t = time.localtime()
    sweep = getattr(render_texture, "_sweep", True)
    sec = (time.time() % 60) if sweep else float(t.tm_sec)

    def paint(cr):
        draw_rolex(cr, size, size, t.tm_hour, t.tm_min, sec, t.tm_mday)

    return WB.render_texture(size, size, paint, scale=scale)


CSS_DEBUG = """
window.rolex { background-color: rgba(40,40,40,1); border: 4px solid red; }
window.rolex picture { background-color: rgba(40,40,40,1); }
"""


class RolexWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,  # debug: permite varias instancias
            flags=WB.APP_FLAGS,
        )
        self.cfg = load_config()
        self.win = None
        self.image = None
        self._timer_id = None

    def do_activate(self):
        print("[rolex] activate: creando ventana...", flush=True)
        if self.win:
            print("[rolex] ventana ya existia, present...", flush=True)
            self.win.present()
            return

        size = int(self.cfg.get("size", 340))
        self.win = WB.make_window(
            self, "rolex",
            "Rolex Submariner" + (" [DEBUG]" if DEBUG else ""),
            size, size, self.cfg, DEBUG,
        )
        WB.install_css("rolex", DEBUG, debug_css=CSS_DEBUG)

        self.image = WB.make_picture(size, size)
        self.win.set_child(self.image)

        # Arrastre (boton izquierdo) via protocolo Wayland toplevel.begin_move
        drag = WB.wire_drag(self.image, self.win, lambda: self.cfg.get("locked"))
        drag.connect("drag-end", self.on_drag_end)

        # Click derecho -> menu (firma GTK4: pressed(n_press, x, y))
        WB.wire_click(self.image, 3, self.on_right_click)

        # Doble click izquierdo -> bloquear/desbloquear
        WB.wire_click(self.image, 1, self.on_left_click)

        WB.wire_keys(self.win, self.on_key)

        # Si el monitor es HiDPI (o cambia), re-render con el buffer correcto.
        self.win.connect("notify::scale-factor", lambda *_: self.refresh())

        self.win.present()
        print(f"[rolex] ventana presentada ({size}x{size}). Buscala como 'Rolex Submariner' con Alt+Tab.", flush=True)
        print("[rolex] Si no la ves: cambia al workspace actual y mira Activities/Overview.", flush=True)
        self.refresh()
        self.restart_timer()
        # confirma que el timer sigue vivo y la ventana mapeada
        GLib.timeout_add(2000, self._confirm_visible)

    # ---- render ----
    _frames_logged = 0

    def refresh(self):
        size = int(self.cfg.get("size", 340))
        render_texture._sweep = bool(self.cfg.get("sweep", True))
        scale = WB.widget_scale(self.win)
        try:
            tex = render_texture(size, scale=scale)
            self.image.set_paintable(tex)
            self.image.set_size_request(size, size)
            if RolexWidget._frames_logged < 3:
                RolexWidget._frames_logged += 1
                print(f"[rolex] textura {size}px (buffer {size * scale}px, escala x{scale}) aplicada a Picture", flush=True)
        except Exception as e:
            print(f"[rolex] ERROR render: {e}", file=sys.stderr, flush=True)

    def restart_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        interval = 50 if self.cfg.get("sweep") else 1000
        self._timer_id = GLib.timeout_add(interval, self.on_tick)

    def on_tick(self):
        self.refresh()
        return True

    def _confirm_visible(self):
        try:
            mapped = self.win.get_mapped() if hasattr(self.win, "get_mapped") else "?"
            p = self.image.get_paintable()
            info = f"{p.get_intrinsic_width()}x{p.get_intrinsic_height()}" if p else "SIN-PAINTABLE"
            print(f"[rolex] check 2s: mapped={mapped} paintable={info}", flush=True)
        except Exception as e:
            print(f"[rolex] check error: {e}", flush=True)
        return False

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

    def on_right_click(self, gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        WB.popup_menu(self.image, x, y, self, [
            ("Sweep suave ✓" if self.cfg.get("sweep") else "Sweep suave",
             "sweep", self.act_sweep),
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
            return True
        if WB.is_bigger_key(name):
            self.resize_by(40)
            return True
        if WB.is_smaller_key(name):
            self.resize_by(-40)
            return True
        return False

    # ---- acciones ----
    def act_sweep(self, *_):
        self.cfg["sweep"] = not self.cfg.get("sweep", True)
        save_config(self.cfg)
        self.restart_timer()

    def act_lock(self, *_):
        WB.toggle_locked(self.cfg, CONFIG_PATH)

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

    def act_quit(self, *_):
        self.quit()

    def resize_by(self, delta):
        size = max(100, min(600, int(self.cfg.get("size", 340)) + delta))
        self.cfg["size"] = size
        self.win.set_default_size(size, size)
        self.refresh()
        self._save_position()


def main():
    app = RolexWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
