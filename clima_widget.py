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

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import widget_base as WB
from clima_draw import draw_clima

APP_ID = "com.vibes.clima-widget"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "clima_config.json")
CACHE_PATH = os.path.join(BASE_DIR, ".clima_cache.json")
DEBUG = os.environ.get("CLIMA_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--debug"]

ASPECT = 0.62  # vertical tipo agenda
MIN_H, MAX_H = 100, 750
DEFAULT_H = 540
FETCH_EVERY = 20 * 60

DEFAULT_CONFIG = {
    "city": "Puebla",
    "lat": 19.04778,
    "lon": -98.20723,
    "height": DEFAULT_H,
    "locked": False,
    "opacity": 1.0,
    "x": -1,
    "y": -1,
}

DOW_ES = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]

_state = {"data": None, "offline": False, "updated": "", "fetching": False}


def load_config():
    return WB.load_config(
        CONFIG_PATH, DEFAULT_CONFIG,
        int_ranges={"height": (MIN_H, MAX_H, DEFAULT_H)},
        float_ranges={
            "lat": (-90.0, 90.0, 19.04778),
            "lon": (-180.0, 180.0, -98.20723),
            "opacity": (0.1, 1.0, 1.0),
        },
    )


def save_config(cfg):
    WB.save_config(CONFIG_PATH, cfg)


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
            d = parse_payload(cached, cfg.get("city", "Puebla"))
            # Sin fetch fresco en esta sesion: marcar como offline/cache
            d["offline"] = True
            return d
        except Exception:
            pass
    return {"city": cfg.get("city", "Puebla"), "temp": None, "code": 3,
            "days": [], "updated": "", "offline": True}


def render_texture(width, height, data, locked=False, scale=WB.SCALE):
    def paint(cr):
        draw_clima(cr, width, height, data, locked)

    return WB.render_texture(width, height, paint, scale=scale)


class ClimaWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,
            flags=WB.APP_FLAGS,
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

        w, h = self.widget_size()
        self.win = WB.make_window(
            self, "clima",
            "Clima Dorado" + (" [DEBUG]" if DEBUG else ""),
            w, h, self.cfg, DEBUG,
        )
        WB.install_css("clima", DEBUG)

        self.image = WB.make_picture(w, h)
        self.win.set_child(self.image)

        drag = WB.wire_drag(self.image, self.win, lambda: self.cfg.get("locked"))
        drag.connect("drag-end", self.on_drag_end)

        WB.wire_click(self.image, 3, self.on_right_click)

        WB.wire_click(self.image, 1, self.on_left_click)

        WB.wire_keys(self.win, self.on_key)

        # Si el monitor es HiDPI (o cambia), re-render con el buffer correcto.
        self.win.connect("notify::scale-factor", lambda *_: self.refresh())

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
            tex = render_texture(w, h, data, locked,
                                 scale=WB.widget_scale(self.win))
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

    def _save_position(self):
        """Guarda la posicion actual de la ventana en config (best-effort)."""
        WB.store_position(self.win, self.cfg, CONFIG_PATH)

    def on_drag_end(self, gesture, _offset_x, _offset_y):
        """Guardar posicion despues de arrastrar."""
        self._save_position()

    def on_left_click(self, gesture, n_press, x, y):
        if n_press == 2:
            WB.toggle_locked(self.cfg, CONFIG_PATH)
            self.refresh()

    def on_right_click(self, gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        WB.popup_menu(self.image, x, y, self, [
            ("Actualizar ahora", "now", self.act_now),
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
            self.refresh()
            return True
        if nl == "r":
            refresh_data_async(self.cfg, self.refresh)
            return True
        if WB.is_bigger_key(name):
            self.resize_by(40)
            return True
        if WB.is_smaller_key(name):
            self.resize_by(-40)
            return True
        return False

    def act_now(self, *_):
        refresh_data_async(self.cfg, self.refresh)

    def act_lock(self, *_):
        WB.toggle_locked(self.cfg, CONFIG_PATH)
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
        w = int(h * ASPECT)
        self.win.set_default_size(w, h)
        self.refresh()
        self._save_position()


def main():
    app = ClimaWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
