#!/usr/bin/env python3
"""Widget Monitor Dorado para Wayland + GNOME.

Misma filosofia que Reloj/Agenda:
- Ventana GTK4 transparente, sin decoracion, que no roba foco.
- Render offscreen con pycairo -> Gtk.Picture via Gdk.MemoryTexture.
- Arrastre Wayland, click derecho con menu, doble-click/L bloqueo.
- 5 diales circulares: CPU, RAM, VRAM, GPU, DISCO + minis EFI/SWAP.
"""

import os
import shutil
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import i18n
import widget_base as WB
from sysmon_draw import draw_sysmon

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

APP_ID = "com.vibes.sysmon-widget"
CONFIG_PATH = WB.config_path("sysmon_config.json")
DEBUG = os.environ.get("SYSMON_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--debug"]

ASPECT = 2.7  # apaisado: 6 diales en horizontal
MIN_H, MAX_H = 100, 500
DEFAULT_H = 320

DEFAULT_CONFIG = {
    "height": DEFAULT_H,
    "locked": False,
    "opacity": 1.0,
    "x": -1,
    "y": -1,
}

_gpu_cache = {"t": 0.0, "data": None}
_net_state = {"t": None, "recv": None, "sent": None, "max": 1.0}


def _fmt_rate(mbps):
    if mbps >= 1000:
        return f"{mbps / 1000:.2f} Gb/s"
    if mbps >= 1:
        return f"{mbps:.1f} Mb/s"
    return f"{mbps * 1000:.0f} Kb/s"


def net_rates():
    """Devuelve (down_mbps, up_mbps, total_mbps, pct) con auto-escala de sesion."""
    if not HAS_PSUTIL:
        return None
    try:
        io = psutil.net_io_counters()
        now = time.time()
        st = _net_state
        if st["t"] is None:
            st.update(t=now, recv=io.bytes_recv, sent=io.bytes_sent)
            return (0.0, 0.0, 0.0, 0.0)
        dt = max(0.2, now - st["t"])
        down = (io.bytes_recv - st["recv"]) * 8 / dt / 1e6
        up = (io.bytes_sent - st["sent"]) * 8 / dt / 1e6
        down = max(0.0, down)
        up = max(0.0, up)
        total = down + up
        st.update(t=now, recv=io.bytes_recv, sent=io.bytes_sent,
                  max=max(st["max"], total, 1.0))
        pct = min(100.0, total / st["max"] * 100.0)
        return (down, up, total, pct)
    except Exception:
        return None


def load_config():
    return WB.load_config(
        CONFIG_PATH, DEFAULT_CONFIG,
        int_ranges={"height": (MIN_H, MAX_H, DEFAULT_H)},
        float_ranges={"opacity": (0.1, 1.0, 1.0)},
    )


def save_config(cfg):
    WB.save_config(CONFIG_PATH, cfg)


def _gb(n):
    return n / (1024 ** 3)


def cpu_temp():
    if not HAS_PSUTIL:
        return None
    try:
        temps = psutil.sensors_temperatures() or {}
        for key in ("k10temp", "coretemp", "zenpower", "acpitz"):
            if key in temps and temps[key]:
                return float(temps[key][0].current)
        for entries in temps.values():
            if entries:
                return float(entries[0].current)
    except Exception:
        pass
    return None


def query_nvidia():
    """Devuelve (gpu_pct, vram_used_mib, vram_total_mib, temp) o None."""
    now = time.time()
    if now - _gpu_cache["t"] < 2.0 and _gpu_cache["data"] is not None:
        return _gpu_cache["data"]
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,"
             "memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        line = (out.stdout or "").strip().splitlines()
        if not line:
            return None
        parts = [p.strip() for p in line[0].split(",")]
        res = (float(parts[0]), float(parts[1]), float(parts[2]),
               float(parts[3]))
        _gpu_cache.update(t=now, data=res)
        return res
    except Exception:
        return None


def collect():
    """Junta todas las metricas en el dict que espera draw_sysmon."""
    cpu_pct, cpu_sub = 0.0, "sin psutil"
    ram_pct, ram_sub = 0.0, ""
    ram_main = "--"
    disk_pct, disk_main, disk_sub = 0.0, "--", "/"
    efi_pct, efi_text = 0.0, "no montado"
    swap_pct, swap_text = 0.0, "--"
    vram_pct, vram_main, vram_sub = 0.0, "N/A", "sin nvidia-smi"
    gpu_pct, gpu_main, gpu_sub = 0.0, "N/A", ""
    net_pct, net_main, net_sub = 0.0, "0 Kb/s", "↓0 ↑0"

    if HAS_PSUTIL:
        try:
            cpu_pct = float(psutil.cpu_percent(interval=None))
        except Exception:
            cpu_pct = 0.0
        try:
            ncpu = psutil.cpu_count() or 0
        except Exception:
            ncpu = 0
        t = cpu_temp()
        cpu_sub = f"{t:.0f}C · {ncpu} hilos" if t else f"{ncpu} hilos"
        try:
            vm = psutil.virtual_memory()
            ram_pct = float(vm.percent)
            ram_main = f"{vm.percent:.0f}%"
            ram_sub = f"{_gb(vm.used):.1f}/{_gb(vm.total):.1f}GB"
        except Exception:
            pass
        try:
            du = psutil.disk_usage("/")
            disk_pct = float(du.percent)
            disk_main = f"{du.percent:.0f}%"
            disk_sub = f"{_gb(du.used):.0f}/{_gb(du.total):.0f}GB"
        except Exception:
            pass
        try:
            due = psutil.disk_usage("/boot/efi")
            efi_pct = float(due.percent)
            efi_text = f"{due.used // 1024 // 1024}M/{_gb(due.total):.1f}G"
        except Exception:
            pass
        try:
            sw = psutil.swap_memory()
            swap_pct = float(sw.percent)
            swap_text = f"{_gb(sw.used):.1f}/{_gb(sw.total):.1f}G"
        except Exception:
            pass
        cpu_main = f"{cpu_pct:.0f}%"
    else:
        cpu_main = "--"

    nv = query_nvidia()
    if nv:
        g_pct, vu, vt, temp = nv
        gpu_pct = g_pct
        gpu_main = f"{g_pct:.0f}%"
        gpu_sub = f"{temp:.0f}C"
        vram_pct = (vu / vt * 100.0) if vt else 0.0
        vram_main = f"{vram_pct:.0f}%"
        vram_sub = f"{vu / 1024:.1f}/{vt / 1024:.1f}GB {temp:.0f}C"

    nr = net_rates()
    if nr:
        down, up, total, pct = nr
        net_pct = pct
        net_main = _fmt_rate(total)
        if total >= 1:
            net_sub = f"↓{down:.1f} ↑{up:.1f} Mb/s"
        else:
            net_sub = f"↓{down * 1000:.0f} ↑{up * 1000:.0f} Kb/s"

    load = ""
    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()[0]
    except Exception:
        pass
    foot = f"load {load}" if load else ""

    return {
        "title": "MONITOR",
        "dials": [
            {"label": "CPU", "pct": cpu_pct, "main": cpu_main, "sub": cpu_sub},
            {"label": "RAM", "pct": ram_pct, "main": ram_main, "sub": ram_sub},
            {"label": "VRAM", "pct": vram_pct, "main": vram_main, "sub": vram_sub},
            {"label": "GPU", "pct": gpu_pct, "main": gpu_main, "sub": gpu_sub},
            {"label": i18n._("DISK"), "pct": disk_pct, "main": disk_main, "sub": disk_sub},
            {"label": i18n._("NET"), "pct": net_pct, "main": net_main, "sub": net_sub},
        ],
        "minis": [
            {"label": "EFI", "pct": efi_pct, "text": efi_text},
            {"label": "SWAP", "pct": swap_pct, "text": swap_text},
        ],
        "footer": foot,
    }


def render_texture(width, height, data, locked=False, scale=WB.SCALE):
    def paint(cr):
        draw_sysmon(cr, width, height, data, locked)

    return WB.render_texture(width, height, paint, scale=scale)


class SysmonWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,
            flags=WB.APP_FLAGS,
        )
        self.cfg = load_config()
        self.win = None
        self.image = None
        self._timer_id = None
        if HAS_PSUTIL:
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                pass

    def do_activate(self):
        print("[sysmon] activate: creando ventana...", flush=True)
        if self.win:
            self.win.present()
            return

        w, h = self.widget_size()
        self.win = WB.make_window(
            self, "sysmon",
            "Monitor Dorado" + (" [DEBUG]" if DEBUG else ""),
            w, h, self.cfg, DEBUG,
        )
        WB.install_css("sysmon", DEBUG)

        self.image = WB.make_picture(w, h)
        self.win.set_child(self.image)

        drag = WB.wire_drag(self.image, self.win, lambda: self.cfg.get("locked"))
        drag.connect("drag-end", self.on_drag_end)

        WB.wire_click(self.image, 3, self.on_right_click)

        WB.wire_click(self.image, 1, self.on_left_click)

        WB.wire_keys(self.win, self.on_key)

        # Si el monitor es HiDPI (o cambia), re-render con el buffer correcto.
        self.win.connect("notify::scale-factor", lambda *_: self.refresh(force=True))

        self.win.present()
        print(f"[sysmon] ventana presentada ({w}x{h}).", flush=True)
        self.refresh(force=True)
        self.restart_timer()

    def widget_size(self):
        h = int(self.cfg.get("height", DEFAULT_H))
        return int(h * ASPECT), h

    def refresh(self, force=False):
        w, h = self.widget_size()
        data = collect()
        locked = bool(self.cfg.get("locked", False))
        try:
            tex = render_texture(w, h, data, locked,
                                 scale=WB.widget_scale(self.win))
            self.image.set_paintable(tex)
            self.image.set_size_request(w, h)
        except Exception as e:
            print(f"[sysmon] ERROR render: {e}", file=sys.stderr, flush=True)

    def restart_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        self._timer_id = GLib.timeout_add(1000, self.on_tick)

    def on_tick(self):
        self.refresh()
        return True

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
            self.refresh(force=True)

    def on_right_click(self, gesture, n_press, x, y):
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

    def on_key(self, _ctl, keyval, _keycode, _state):
        name = Gdk.keyval_name(keyval) or ""
        nl = name.lower()
        if WB.is_quit_key(name, nl):
            self.quit()
            return True
        if WB.is_lock_key(nl):
            WB.toggle_locked(self.cfg, CONFIG_PATH)
            self.refresh(force=True)
            print(f"[sysmon] {'bloqueado' if self.cfg.get('locked') else 'desbloqueado'}", flush=True)
            return True
        if WB.is_bigger_key(name):
            self.resize_by(40)
            return True
        if WB.is_smaller_key(name):
            self.resize_by(-40)
            return True
        return False

    def act_lock(self, *_):
        WB.toggle_locked(self.cfg, CONFIG_PATH)
        self.refresh(force=True)

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

    def act_settings(self, *_):
        WB.settings_dialog(self.win, self.cfg, [
            ("height", "Height", "spin", (MIN_H, MAX_H, 10, 0)),
            ("opacity", "Opacity", "spin", (0.1, 1.0, 0.05, 2)),
        ], self.apply_settings)

    def apply_settings(self, cfg):
        WB.save_config(CONFIG_PATH, cfg)
        try:
            self.win.set_opacity(float(cfg.get("opacity", 1.0)))
        except (TypeError, ValueError):
            pass
        h = int(cfg.get("height", DEFAULT_H))
        self.win.set_default_size(int(h * ASPECT), h)
        self.refresh(force=True)

    def act_quit(self, *_):
        self.quit()

    def resize_by(self, delta):
        h = max(MIN_H, min(MAX_H, int(self.cfg.get("height", DEFAULT_H)) + delta))
        self.cfg["height"] = h
        WB.save_config(CONFIG_PATH, self.cfg)
        w = int(h * ASPECT)
        self.win.set_default_size(w, h)
        self.refresh(force=True)
        self._save_position()


def main():
    app = SysmonWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
