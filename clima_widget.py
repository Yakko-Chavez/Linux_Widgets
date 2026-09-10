#!/usr/bin/env python3
"""Widget Clima Dorado para Wayland + GNOME (Puebla, Open-Meteo sin key).

Misma filosofia que Rolex/Agenda/Monitor:
- Ventana GTK4 transparente, sin decoracion, que no roba foco.
- Render offscreen con pycairo -> Gtk.Picture via Gdk.MemoryTexture.
- Arrastre Wayland, click derecho con menu, doble-click/L bloqueo.
- Fetch Open-Meteo en hilo cada 20 min + cache en disco (offline).
"""

import datetime
import json
import os
import sys
import threading
import time
import urllib.request

import cairo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from clima_draw import draw_clima

APP_ID = "com.vibes.clima-widget"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "clima_config.json")
CACHE_PATH = os.path.join(BASE_DIR, ".clima_cache.json")
DEBUG = os.environ.get("CLIMA_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--debug"]

ASPECT = 0.62  # vertical tipo agenda
MIN_H, MAX_H = 420, 750
DEFAULT_H = 540
FETCH_EVERY = 20 * 60

DEFAULT_CONFIG = {
    "city": "Puebla",
    "lat": 19.04778,
    "lon": -98.20723,
    "height": DEFAULT_H,
    "locked": False,
    "opacity": 1.0,
}

DOW_ES = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]

_state = {"data": None, "offline": False, "updated": "", "fetching": False}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        cfg["height"] = max(MIN_H, min(MAX_H, int(cfg.get("height", DEFAULT_H))))
    except (TypeError, ValueError):
        cfg["height"] = DEFAULT_H
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"No se pudo guardar config: {e}", file=sys.stderr)


def _save_cache(payload):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        pass


def _load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def fetch_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        "&timezone=auto&forecast_days=6"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "clima-widget/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def parse_payload(payload, city):
    cur = (payload or {}).get("current", {})
    daily = (payload or {}).get("daily", {})
    times = daily.get("time", [])
    codes = daily.get("weather_code", [])
    mx = daily.get("temperature_2m_max", [])
    mn = daily.get("temperature_2m_min", [])
    days = []
    for i in range(1, min(6, len(times))):
        try:
            dt = datetime.date.fromisoformat(times[i])
            dow = DOW_ES[dt.weekday()]
        except (ValueError, IndexError):
            dow = ""
        days.append({
            "dow": dow,
            "code": codes[i] if i < len(codes) else 3,
            "max": mx[i] if i < len(mx) else None,
            "min": mn[i] if i < len(mn) else None,
        })
    tstr = str(cur.get("time", ""))
    hhmm = tstr[11:16] if len(tstr) >= 16 else ""
    return {
        "city": city,
        "temp": cur.get("temperature_2m"),
        "code": cur.get("weather_code", 3),
        "apparent": cur.get("apparent_temperature"),
        "hum": cur.get("relative_humidity_2m"),
        "wind": cur.get("wind_speed_10m"),
        "days": days,
        "updated": hhmm,
        "offline": _state["offline"],
    }


def refresh_data_async(cfg, on_done):
    if _state["fetching"]:
        return
    _state["fetching"] = True

    def _work():
        try:
            payload = fetch_weather(cfg.get("lat"), cfg.get("lon"))
            _state["offline"] = False
            _save_cache(payload)
            data = parse_payload(payload, cfg.get("city", "Puebla"))
            _state.update(data=data, updated=data.get("updated", ""))
        except Exception as e:
            print(f"[clima] fetch fallo ({e}), usando cache", flush=True)
            cached = _load_cache()
            if cached:
                try:
                    data = parse_payload(cached, cfg.get("city", "Puebla"))
                    data["offline"] = True
                    _state.update(data=data, offline=True)
                except Exception:
                    pass
            else:
                _state["offline"] = True
        finally:
            _state["fetching"] = False
            GLib.idle_add(on_done)

    threading.Thread(target=_work, daemon=True).start()


def current_data(cfg):
    if _state["data"] is not None:
        d = dict(_state["data"])
        d["offline"] = _state["offline"]
        return d
    cached = _load_cache()
    if cached:
        try:
            return parse_payload(cached, cfg.get("city", "Puebla"))
        except Exception:
            pass
    return {"city": cfg.get("city", "Puebla"), "temp": None, "code": 3,
            "days": [], "updated": "", "offline": True}


def render_texture(width, height, data, locked=False):
    scale = 2
    px_w, px_h = int(width * scale), int(height * scale)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, px_w, px_h)
    cr = cairo.Context(surf)
    cr.scale(scale, scale)
    draw_clima(cr, width, height, data, locked)
    surf.flush()
    buf = GLib.Bytes.new(bytes(surf.get_data()))
    return Gdk.MemoryTexture.new(
        px_w, px_h, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, buf,
        surf.get_stride(),
    )


CSS = """
window.clima { background-color: transparent; }
window.clima picture { background-color: transparent; }
"""

CSS_DEBUG = """
window.clima { background-color: rgba(40,40,40,1); border: 4px solid gold; }
window.clima picture { background-color: rgba(40,40,40,1); }
"""


class ClimaWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,
            flags=Gio.ApplicationFlags.ALLOW_REPLACEMENT
            | Gio.ApplicationFlags.REPLACE,
        )
        self.cfg = load_config()
        self.win = None
        self.image = None
        self._timer_id = None
        self._fetch_id = None

    def do_activate(self):
        print("[clima] activate: creando ventana...", flush=True)
        if self.win:
            self.win.present()
            return

        self.win = Gtk.Window(application=self)
        self.win.add_css_class("clima")
        self.win.set_title("Clima Dorado" + (" [DEBUG]" if DEBUG else ""))
        self.win.set_decorated(True if DEBUG else False)
        self.win.set_resizable(False)
        self.win.set_focus_on_click(False)

        w, h = self.widget_size()
        self.win.set_default_size(w, h)

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
        self.image.set_size_request(w, h)
        self.image.set_can_target(True)
        self.win.set_child(self.image)

        drag = Gtk.GestureDrag.new()
        drag.set_button(1)
        drag.connect("drag-begin", self.on_drag_begin)
        self.image.add_controller(drag)

        right = Gtk.GestureClick.new()
        right.set_button(3)
        right.connect("pressed", self.on_right_click)
        self.image.add_controller(right)

        dbl = Gtk.GestureClick.new()
        dbl.set_button(1)
        dbl.connect("pressed", self.on_left_click)
        self.image.add_controller(dbl)

        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self.on_key)
        self.win.add_controller(keys)

        self.win.present()
        print(f"[clima] ventana presentada ({w}x{h}).", flush=True)
        self.refresh()
        self.restart_timer()
        refresh_data_async(self.cfg, self.refresh)
        self._fetch_id = GLib.timeout_add_seconds(FETCH_EVERY, self.on_fetch)

    def widget_size(self):
        h = int(self.cfg.get("height", DEFAULT_H))
        return int(h * ASPECT), h

    def refresh(self):
        w, h = self.widget_size()
        data = current_data(self.cfg)
        locked = bool(self.cfg.get("locked", False))
        try:
            tex = render_texture(w, h, data, locked)
            self.image.set_paintable(tex)
            self.image.set_size_request(w, h)
        except Exception as e:
            print(f"[clima] ERROR render: {e}", file=sys.stderr, flush=True)

    def restart_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        self._timer_id = GLib.timeout_add(60_000, self.on_tick)

    def on_tick(self):
        self.refresh()
        return True

    def on_fetch(self):
        refresh_data_async(self.cfg, self.refresh)
        return True

    def on_drag_begin(self, gesture, x, y):
        if self.cfg.get("locked"):
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        try:
            surf = self.win.get_surface()
            device = gesture.get_current_event_device()
            button = gesture.get_current_button()
            ts = gesture.get_current_event_time()
            surf.begin_move(device, button, x, y, ts)
        except Exception as e:
            print(f"Move: usa Super+arrastrar en GNOME ({e})", file=sys.stderr)

    def on_left_click(self, gesture, n_press, x, y):
        if n_press == 2:
            self.cfg["locked"] = not self.cfg.get("locked", False)
            save_config(self.cfg)
            self.refresh()

    def on_right_click(self, gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        menu = Gio.Menu()
        menu.append("Actualizar ahora", "app.now")
        menu.append("Bloquear clicks ✓" if self.cfg.get("locked") else "Bloquear clicks", "app.lock")
        menu.append("Tamaño +", "app.bigger")
        menu.append("Tamaño −", "app.smaller")
        menu.append("Salir", "app.quit")

        for name in ("now", "lock", "bigger", "smaller", "quit"):
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
            self.refresh()
            return True
        if nl == "r":
            refresh_data_async(self.cfg, self.refresh)
            return True
        if name in ("plus", "KP_Add", "equal"):
            self.resize_by(40)
            return True
        if name in ("minus", "KP_Subtract"):
            self.resize_by(-40)
            return True
        return False

    def act_now(self, *_):
        refresh_data_async(self.cfg, self.refresh)

    def act_lock(self, *_):
        self.cfg["locked"] = not self.cfg.get("locked", False)
        save_config(self.cfg)
        self.refresh()

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

    def act_quit(self, *_):
        self.quit()

    def resize_by(self, delta):
        h = max(MIN_H, min(MAX_H, int(self.cfg.get("height", DEFAULT_H)) + delta))
        self.cfg["height"] = h
        save_config(self.cfg)
        w = int(h * ASPECT)
        self.win.set_default_size(w, h)
        self.refresh()


def main():
    app = ClimaWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
