#!/usr/bin/env python3
"""Widget de escritorio Rolex Submariner para Wayland + GNOME.

Ventana GTK4 transparente, sin decoracion, solo visual.
- Render offscreen con pycairo -> Gtk.Image (NO necesita python3-gi-cairo,
  que falta en Ubuntu base y requiere sudo para instalar).
- Movimiento sweep suave o tick segun config.
- Arrastre con Super+drag de GNOME o gesto (Wayland: el compositor decide posicion).
- Click derecho: menu. Doble click / L: bloquear.
"""

import json
import os
import sys
import time

import argparse
import cairo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

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
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # Sanitizar: size dentro de 200-600, eliminar clave legacy always_on_top
    # (Wayland/GNOME no permite keep-above desde la app).
    cfg.pop("always_on_top", None)
    try:
        cfg["size"] = max(200, min(600, int(cfg.get("size", 340))))
    except (TypeError, ValueError):
        cfg["size"] = 340
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"No se pudo guardar config: {e}", file=sys.stderr)


def render_texture(size):
    """Renderiza el reloj a Gdk.Texture 100% en memoria.

    Sin archivos, sin GdkPixbuf, sin puente cairo de PyGObject:
    el layout en memoria de cairo ARGB32 (little-endian) coincide con
    GDK_MEMORY_B8G8R8A8_PREMULTIPLIED. Elimina de raiz la ventana
    transparente (carreras PNG + cache de Gtk.Image).
    """
    scale = 2  # rango valido 200-600px: siempre x2 para nitidez HiDPI
    px = int(size * scale)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, px, px)
    cr = cairo.Context(surf)
    cr.scale(scale, scale)
    t = time.localtime()
    sweep = getattr(render_texture, "_sweep", True)
    sec = (time.time() % 60) if sweep else float(t.tm_sec)
    draw_rolex(cr, size, size, t.tm_hour, t.tm_min, sec, t.tm_mday)
    surf.flush()
    data = GLib.Bytes.new(bytes(surf.get_data()))
    return Gdk.MemoryTexture.new(
        px, px, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, data, surf.get_stride()
    ), px


CSS = """
window.rolex { background-color: transparent; }
window.rolex picture { background-color: transparent; }
"""

CSS_DEBUG = """
window.rolex { background-color: rgba(40,40,40,1); border: 4px solid red; }
window.rolex picture { background-color: rgba(40,40,40,1); }
"""


class RolexWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,  # debug: permite varias instancias
            flags=Gio.ApplicationFlags.ALLOW_REPLACEMENT
            | Gio.ApplicationFlags.REPLACE,
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

        self.win = Gtk.Window(application=self)
        self.win.add_css_class("rolex")
        self.win.set_title("Rolex Submariner" + (" [DEBUG]" if DEBUG else ""))
        self.win.set_decorated(True if DEBUG else False)
        self.win.set_resizable(False)
        self.win.set_focus_on_click(False)

        size = int(self.cfg.get("size", 340))
        self.win.set_default_size(size, size)

        css = Gtk.CssProvider()
        css.load_from_data((CSS_DEBUG if DEBUG else CSS).encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        try:
            self.win.set_opacity(float(self.cfg.get("opacity", 1.0)))
        except Exception:
            pass

        self.image = Gtk.Picture()
        self.image.set_content_fit(Gtk.ContentFit.FILL)
        self.image.set_can_shrink(False)
        self.image.set_size_request(size, size)
        self.image.set_can_target(True)
        self.win.set_child(self.image)

        # Arrastre (boton izquierdo) via protocolo Wayland toplevel.begin_move
        drag = Gtk.GestureDrag.new()
        drag.set_button(1)
        drag.connect("drag-begin", self.on_drag_begin)
        self.image.add_controller(drag)

        # Click derecho -> menu (firma GTK4: pressed(n_press, x, y))
        right = Gtk.GestureClick.new()
        right.set_button(3)
        right.connect("pressed", self.on_right_click)
        self.image.add_controller(right)

        # Doble click izquierdo -> bloquear/desbloquear
        dbl = Gtk.GestureClick.new()
        dbl.set_button(1)
        dbl.connect("pressed", self.on_left_click)
        self.image.add_controller(dbl)

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self.on_key)
        self.win.add_controller(keys)

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
        try:
            tex, px = render_texture(size)
            self.image.set_paintable(tex)
            self.image.set_size_request(size, size)
            if RolexWidget._frames_logged < 3:
                RolexWidget._frames_logged += 1
                print(f"[rolex] textura {size}px (buffer {px}px) aplicada a Picture", flush=True)
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
    def on_drag_begin(self, gesture, x, y):
        if self.cfg.get("locked"):
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        try:
            surf = self.win.get_surface()
            device = gesture.get_current_event_device()
            button = gesture.get_current_button()
            ts = gesture.get_current_event_time()
            # begin_move(device, button, x_root, y_root, timestamp)
            surf.begin_move(device, button, x, y, ts)
        except Exception as e:
            print(f"Move: usa Super+arrastrar en GNOME ({e})", file=sys.stderr)

    def on_left_click(self, gesture, n_press, x, y):
        if n_press == 2:
            self.cfg["locked"] = not self.cfg.get("locked", False)
            save_config(self.cfg)

    def on_right_click(self, gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        menu = Gio.Menu()
        menu.append("Sweep suave ✓" if self.cfg.get("sweep") else "Sweep suave", "app.sweep")
        menu.append("Bloquear clicks ✓" if self.cfg.get("locked") else "Bloquear clicks", "app.lock")
        menu.append("Tamaño +", "app.bigger")
        menu.append("Tamaño −", "app.smaller")
        menu.append("Salir", "app.quit")

        for name in ("sweep", "lock", "bigger", "smaller", "quit"):
            if self.lookup_action(name) is None:
                a = Gio.SimpleAction.new(name, None)
                a.connect("activate", getattr(self, f"act_{name}"))
                self.add_action(a)

        pop = Gtk.PopoverMenu.new_from_model(menu)
        pop.set_parent(self.image)
        pop.set_pointing_to(Gdk.Rectangle(int(x), int(y), 1, 1))
        pop.popup()

    def on_key(self, _ctl, keyval, _keycode, _state):
        name = Gdk.keyval_name(keyval) or ""
        nl = name.lower()
        if nl in ("q", "escape"):
            self.quit()
            return True
        if nl == "l":
            self.cfg["locked"] = not self.cfg.get("locked", False)
            save_config(self.cfg)
            return True
        if name in ("plus", "KP_Add", "equal"):
            self.resize_by(40)
            return True
        if name in ("minus", "KP_Subtract"):
            self.resize_by(-40)
            return True
        return False

    # ---- acciones ----
    def act_sweep(self, *_):
        self.cfg["sweep"] = not self.cfg.get("sweep", True)
        save_config(self.cfg)
        self.restart_timer()

    def act_lock(self, *_):
        self.cfg["locked"] = not self.cfg.get("locked", False)
        save_config(self.cfg)

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

    def act_quit(self, *_):
        self.quit()

    def resize_by(self, delta):
        size = max(200, min(600, int(self.cfg.get("size", 340)) + delta))
        self.cfg["size"] = size
        save_config(self.cfg)
        self.win.set_default_size(size, size)
        self.refresh()


def main():
    app = RolexWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
