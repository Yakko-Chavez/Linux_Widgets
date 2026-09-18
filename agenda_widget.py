#!/usr/bin/env python3
"""Widget de escritorio Agenda de Lujo para Wayland + GNOME.

Misma filosofia que el Rolex Submariner:
- Ventana GTK4 transparente, sin decoracion, que no roba foco.
- Render offscreen con pycairo -> Gtk.Picture via Gdk.MemoryTexture.
- Arrastre Wayland, click derecho con menu, doble-click/L bloqueo.
- Calendario mensual navegable, solo fecha del sistema (sin eventos externos).
"""

import os
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import widget_base as WB
from agenda_draw import draw_agenda, header_arrow_zones

APP_ID = "com.vibes.agenda-widget"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "agenda_config.json")
DEBUG = os.environ.get("AGENDA_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--debug"]

ASPECT = 0.70  # ancho = alto * 0.70 (vertical tipo libreta)
MIN_H, MAX_H = 100, 800
DEFAULT_H = 600

DEFAULT_CONFIG = {
    "height": DEFAULT_H,
    "locked": False,
    "opacity": 1.0,
    "monday_first": True,
    "view_year": None,   # None = seguir mes actual del sistema
    "view_month": None,
    "x": -1,
    "y": -1,
}


def load_config():
    return WB.load_config(
        CONFIG_PATH, DEFAULT_CONFIG,
        int_ranges={"height": (MIN_H, MAX_H, DEFAULT_H)},
        float_ranges={"opacity": (0.1, 1.0, 1.0)},
    )


def save_config(cfg):
    WB.save_config(CONFIG_PATH, cfg)


def current_view(cfg):
    """Devuelve (year, month) visibles: config fija o mes actual."""
    vy, vm = cfg.get("view_year"), cfg.get("view_month")
    t = time.localtime()
    if isinstance(vy, int) and isinstance(vm, int) and 1 <= vm <= 12:
        return vy, vm
    return t.tm_year, t.tm_mon


def render_texture(width, height, year, month, today_ymd, monday_first, locked=False, scale=WB.SCALE):
    def paint(cr):
        draw_agenda(cr, width, height, year, month, today_ymd, monday_first, locked)

    return WB.render_texture(width, height, paint, scale=scale)


# Solo los botones de navegacion (el fondo transparente y el modo debug los
# genera widget_base). En debug se usa el estilo dorado de la base.
CSS_NAV = """
window.agenda button.nav {
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
window.agenda button.nav:hover {
  background-color: rgba(201,162,39,0.22);
  background-image: none;
  border-color: rgba(201,162,39,0.65);
}
window.agenda button.nav:active {
  background-color: rgba(201,162,39,0.38);
  background-image: none;
}
window.agenda button.nav:disabled {
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  box-shadow: none;
  outline: none;
}
"""


class AgendaWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,
            flags=WB.APP_FLAGS,
        )
        self.cfg = load_config()
        self.win = None
        self.image = None
        self.btn_prev = None
        self.btn_next = None
        self.btn_today = None
        self._timer_id = None
        self._last_day = None
        self._last_locked = None

    def do_activate(self):
        print("[agenda] activate: creando ventana...", flush=True)
        if self.win:
            self.win.present()
            return

        w, h = self.widget_size()
        self.win = WB.make_window(
            self, "agenda",
            "Agenda de Lujo" + (" [DEBUG]" if DEBUG else ""),
            w, h, self.cfg, DEBUG,
        )
        WB.install_css("agenda", DEBUG, extra=CSS_NAV)

        self.image = WB.make_picture(w, h)

        # Overlay con botones reales: clicks 100% fiables (sin hit-testing
        # por coordenadas ni competencia con el gesto de arrastre). Son
        # transparentes: el visual dorado lo dibuja Cairo debajo.
        overlay = Gtk.Overlay()
        overlay.set_child(self.image)

        self.btn_prev = self._make_nav_button("Mes anterior")
        self.btn_prev.connect("clicked", self._on_prev_clicked)
        self.btn_prev.set_halign(Gtk.Align.START)
        self.btn_prev.set_valign(Gtk.Align.START)
        overlay.add_overlay(self.btn_prev)

        self.btn_next = self._make_nav_button("Mes siguiente")
        self.btn_next.connect("clicked", self._on_next_clicked)
        self.btn_next.set_halign(Gtk.Align.END)
        self.btn_next.set_valign(Gtk.Align.START)
        overlay.add_overlay(self.btn_next)

        self.btn_today = self._make_nav_button("Volver a hoy")
        self.btn_today.connect("clicked", self._on_today_clicked)
        self.btn_today.set_halign(Gtk.Align.FILL)
        self.btn_today.set_valign(Gtk.Align.END)
        overlay.add_overlay(self.btn_today)

        self.win.set_child(overlay)
        self._layout_nav()

        drag = WB.wire_drag(self.image, self.win, lambda: self.cfg.get("locked"))
        drag.connect("drag-end", self.on_drag_end)

        WB.wire_click(self.image, 3, self.on_right_click)

        WB.wire_click(self.image, 1, self.on_left_click)

        WB.wire_keys(self.win, self.on_key)

        # Si el monitor es HiDPI (o cambia), re-render con el buffer correcto.
        self.win.connect("notify::scale-factor", lambda *_: self.refresh(force=True))

        self.win.present()
        print(f"[agenda] ventana presentada ({w}x{h}).", flush=True)
        self.refresh(force=True)
        self.restart_timer()

    # ---- sizes ----
    def widget_size(self):
        h = int(self.cfg.get("height", DEFAULT_H))
        return int(h * ASPECT), h

    # ---- render ----
    def refresh(self, force=False):
        w, h = self.widget_size()
        t = time.localtime()
        today = (t.tm_year, t.tm_mon, t.tm_mday)
        locked = bool(self.cfg.get("locked", False))
        if (not force and today == self._last_day
                and locked == self._last_locked and self.image.get_paintable()):
            return
        self._last_day = today
        self._last_locked = locked
        year, month = current_view(self.cfg)
        try:
            tex = render_texture(
                w, h, year, month, today, bool(self.cfg.get("monday_first", True)),
                locked, scale=WB.widget_scale(self.win),
            )
            self.image.set_paintable(tex)
            self.image.set_size_request(w, h)
            self._layout_nav()
        except Exception as e:
            print(f"[agenda] ERROR render: {e}", file=sys.stderr, flush=True)

    def restart_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        # Revisar cada 30s si cambio el dia; suficiente para un calendario.
        self._timer_id = GLib.timeout_add(30_000, self.on_tick)

    def on_tick(self):
        self.refresh()
        return True

    # ---- navegacion ----
    def shift_month(self, delta):
        year, month = current_view(self.cfg)
        idx = (year * 12 + (month - 1)) + delta
        self.cfg["view_year"] = idx // 12
        self.cfg["view_month"] = idx % 12 + 1
        save_config(self.cfg)
        print(f"[agenda] vista -> {self.cfg['view_year']}-{self.cfg['view_month']:02d}", flush=True)
        self.refresh(force=True)

    def go_today(self):
        self.cfg["view_year"] = None
        self.cfg["view_month"] = None
        save_config(self.cfg)
        print("[agenda] vista -> hoy", flush=True)
        self.refresh(force=True)

    # ---- botones overlay ----
    @staticmethod
    def _make_nav_button(tooltip):
        b = Gtk.Button(label="")
        b.add_css_class("flat")  # sin fondo ni borde del tema Adwaita
        b.add_css_class("nav")
        b.set_tooltip_text(tooltip)
        b.set_focusable(False)
        b.set_focus_on_click(False)
        try:
            b.set_cursor_from_name("pointer")
        except Exception:
            pass
        return b

    def _layout_nav(self):
        """Posiciona los botones transparentes sobre el dibujo Cairo."""
        if self.btn_prev is None:
            return
        w, h = self.widget_size()
        zones = header_arrow_zones(w, h)
        S = 36  # área táctil (visual Cairo r=15 → 30px)
        pcx, pcy, _pr = zones["prev"]
        ncx, ncy, _nr = zones["next"]
        self.btn_prev.set_size_request(S, S)
        self.btn_prev.set_margin_start(int(pcx - S / 2))
        self.btn_prev.set_margin_top(int(pcy - S / 2))
        self.btn_next.set_size_request(S, S)
        self.btn_next.set_margin_end(int(w - (ncx + S / 2)))
        self.btn_next.set_margin_top(int(ncy - S / 2))
        tx, tyy, tw, th = zones["today"]
        self.btn_today.set_size_request(10, int(th))
        self.btn_today.set_margin_start(int(tx))
        self.btn_today.set_margin_end(int(w - (tx + tw)))
        self.btn_today.set_margin_bottom(int(h - (tyy + th)))
        locked = bool(self.cfg.get("locked", False))
        for b in (self.btn_prev, self.btn_next, self.btn_today):
            b.set_sensitive(not locked)

    def _on_prev_clicked(self, _btn):
        if not self.cfg.get("locked"):
            self.shift_month(-1)

    def _on_next_clicked(self, _btn):
        if not self.cfg.get("locked"):
            self.shift_month(1)

    def _on_today_clicked(self, _btn):
        if not self.cfg.get("locked"):
            self.go_today()

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
            self._layout_nav()
            self.refresh(force=True)

    def on_right_click(self, gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        WB.popup_menu(self.image, x, y, self, [
            ("Mes anterior", "prev", self.act_prev),
            ("Mes siguiente", "next", self.act_next),
            ("Ir a hoy", "today", self.act_today),
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
            self._layout_nav()
            self.refresh(force=True)
            print(f"[agenda] {'bloqueado' if self.cfg.get('locked') else 'desbloqueado'}", flush=True)
            return True
        if name in ("Left", "KP_Left"):
            self.shift_month(-1)
            return True
        if name in ("Right", "KP_Right"):
            self.shift_month(1)
            return True
        if name in ("Up", "KP_Up"):
            self.shift_month(-12)
            return True
        if name in ("Down", "KP_Down"):
            self.shift_month(12)
            return True
        if nl in ("h", "t"):
            self.go_today()
            return True
        if WB.is_bigger_key(name):
            self.resize_by(40)
            return True
        if WB.is_smaller_key(name):
            self.resize_by(-40)
            return True
        return False

    # ---- acciones ----
    def act_prev(self, *_):
        self.shift_month(-1)

    def act_next(self, *_):
        self.shift_month(1)

    def act_today(self, *_):
        self.go_today()

    def act_lock(self, *_):
        WB.toggle_locked(self.cfg, CONFIG_PATH)
        self._layout_nav()
        self.refresh(force=True)

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

    def act_quit(self, *_):
        self.quit()

    def resize_by(self, delta):
        h = max(MIN_H, min(MAX_H, int(self.cfg.get("height", DEFAULT_H)) + delta))
        self.cfg["height"] = h
        w = int(h * ASPECT)
        self.win.set_default_size(w, h)
        self.refresh(force=True)
        self._save_position()


def main():
    app = AgendaWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
