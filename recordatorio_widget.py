#!/usr/bin/env python3
"""Widget de escritorio Recordatorio Dorado para Wayland + GNOME.

Misma filosofia que Reloj/Agenda/Clima/Monitor/Cronografo/Calculadora:
- Ventana GTK4 transparente, sin decoracion, que no roba foco.
- Render offscreen con pycairo -> Gtk.Picture via Gdk.MemoryTexture.
- Arrastre Wayland, click derecho con menu, doble-click/L bloqueo.
- Lista vertical de recordatorios puntuales ("en X minutos" o "a las
  HH:MM") con cuenta atras en vivo. Al vencer: sonido (paplay sobre un
  WAV generado con wave+math) + notificacion D-Bus de GNOME (con la
  accion 'Posponer 5 min') + fila con destello dorado pulsante.
- Los recordatorios viven en la config por usuario (~/.config/
  desktop-widgets/recordatorio_config.json) y sobreviven reinicios.
"""

import math
import os
import shutil
import subprocess
import sys
import time
import wave

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

import i18n
import widget_base as WB
from recordatorio_draw import (
    draw_recordatorio,
    format_countdown,
    now_epoch,
    parse_hhmm,
    recordatorio_button_zones,
)

APP_ID = "com.vibes.recordatorio-widget"
CONFIG_PATH = WB.config_path("recordatorio_config.json")
DEBUG = os.environ.get("REC_DEBUG", "") == "1" or "--debug" in sys.argv
if "--debug" in sys.argv:
    sys.argv = [a for a in sys.argv if a != "--debug"]

MIN_H, MAX_H = 100, 750
DEFAULT_H = 520
ASPECT = 0.60  # ancho = alto * ASPECT
MAX_NOTE = 60
SNOOZE_S = 300

DEFAULT_CONFIG = {
    "height": DEFAULT_H,
    "locked": False,
    "opacity": 1.0,
    "sound": True,
    "reminders": [],
}


def _sanitize_reminders(raw):
    out = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        note = str(item.get("note", ""))
        try:
            target = int(float(item.get("target")))
            created = int(float(item.get("created", target)))
        except (TypeError, ValueError):
            continue
        if target <= 0:
            continue
        uid = str(item.get("id") or f"{target}-{created}")
        out.append(
            {"note": note[:MAX_NOTE], "target": target,
             "created": created, "id": uid})
    out.sort(key=lambda r: r["target"])
    return out


def load_config():
    cfg = WB.load_config(
        CONFIG_PATH, DEFAULT_CONFIG,
        int_ranges={"height": (MIN_H, MAX_H, DEFAULT_H)},
        float_ranges={"opacity": (0.1, 1.0, 1.0)},
    )
    cfg["sound"] = bool(cfg.get("sound", True))
    cfg["reminders"] = _sanitize_reminders(cfg.get("reminders", []))
    return cfg


def save_config(cfg):
    WB.save_config(CONFIG_PATH, cfg)


# Solo el '+ Añadir' y las '✕' (el fondo lo genera la base).
CSS_BTN = """
window.recordatorio button.rec {
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  box-shadow: none;
  outline: none;
  color: transparent;
  border-radius: 999px;
  padding: 0;
}
window.recordatorio button.rec:hover {
  background-color: rgba(201,162,39,0.22);
  border-color: rgba(201,162,39,0.65);
}
window.recordatorio button.rec:active {
  background-color: rgba(201,162,39,0.38);
}
window.recordatorio button.rec:disabled {
  background-color: transparent;
  background-image: none;
  border-color: transparent;
  box-shadow: none;
  outline: none;
}
"""

# ---- sonido (sin dependencias: WAV generado + paplay) ----


def tone_path():
    return os.path.join(
        GLib.get_user_cache_dir(), "desktop-widgets", "alarm_tone.wav")


def _write_tone(path):
    """Sirena estridente: 5 ciclos de dos notas (1200/900 Hz) con
    armónico brillante y amplitud plena; fade corto anti-clicks."""
    sample_rate = 22050
    note, gap, cycles = 0.28, 0.10, 5
    fade_n = int(sample_rate * 0.006)
    frames = bytearray()
    for c in range(cycles):
        for f in (1200, 900):
            note_n = int(sample_rate * note)
            for i in range(note_n):
                t = i / sample_rate
                val = 0.95 * (math.sin(2 * math.pi * f * t)
                              + 0.45 * math.sin(2 * math.pi * 2 * f * t)
                              + 0.20 * math.sin(2 * math.pi * 3 * f * t))
                val = max(-1.0, min(1.0, val))
                if i < fade_n:
                    val *= i / fade_n
                elif i > note_n - fade_n:
                    val *= (note_n - i) / fade_n
                frames.extend(
                    int(val * 32767).to_bytes(2, "little", signed=True))
        for _ in range(int(sample_rate * gap)):
            frames.extend(b"\x00\x00")
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(bytes(frames))


def ensure_tone():
    path = tone_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.isfile(path):
            _write_tone(path)
        return path
    except OSError as e:
        print(f"[rec] tono de alarma: {e}", file=sys.stderr)
        return None


PLAYERS = ("paplay", "pw-play", "aplay")


def play_tone():
    path = ensure_tone()
    if path is None:
        return
    player = next((p for p in PLAYERS if shutil.which(p)), None)
    if player is None:
        print("[rec] sin reproductor de audio (paplay/pw-play/aplay)",
              file=sys.stderr)
        return
    try:
        subprocess.Popen(
            [player, path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"[rec] {player}: {e}", file=sys.stderr)


# ---- notificacion D-Bus (sin libnotify) ----


class Notifier:
    """org.freedesktop.Notifications via Gio. Fallback silencioso."""

    def __init__(self, on_action=None):
        self.proxy = None
        self.on_action = on_action  # on_action(nid, action_key)
        self.nid_to_uid = {}

    def _ensure(self):
        if self.proxy is not None:
            return True
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
            )
            proxy.connect("g-signal", self._on_signal)
            self.proxy = proxy
            return True
        except Exception as e:
            print(f"[rec] sin notificaciones D-Bus: {e}", file=sys.stderr)
            self.proxy = False  # no reintentar cada tick
            return False

    def _on_signal(self, _proxy, _sender, sig_name, params):
        if sig_name != "ActionInvoked" or self.on_action is None:
            return
        try:
            nid, action = params.unpack()[0], params.unpack()[1]
        except (IndexError, ValueError):
            return
        self.on_action(nid, action)

    def notify(self, summary, body, actions=(), uid=None):
        if self.proxy is False or not self._ensure():
            return
        acts = []
        for key, label in actions:
            acts += [key, label]
        try:
            res = self.proxy.call_sync(
                "Notify",
                GLib.Variant(
                    "(susssasa{sv}i)",
                    [
                        "Recordatorio Dorado", 0, "dialog-information",
                        summary, body or "", acts, {}, 0,
                    ]),
                Gio.DBusCallFlags.NONE, -1,
            )
            nid = res.unpack()[0]
            if uid is not None:
                self.nid_to_uid[nid] = uid
        except Exception as e:
            print(f"[rec] Notify: {e}", file=sys.stderr)


def render_texture(w, h, rows, now, locked=False, flash=0, scale=WB.SCALE):
    def paint(cr):
        draw_recordatorio(cr, w, h, rows, now, locked=locked, flash_phase=flash)

    return WB.render_texture(w, h, paint, scale=scale)


class ReminderWidget(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=None if DEBUG else APP_ID,
            flags=WB.APP_FLAGS,
        )
        self.cfg = load_config()
        self.win = None
        self.image = None
        self.btn_add = None
        self.btn_del = []
        self._timer_id = None
        self._fired = set()   # ids ya avisados en esta sesion
        self._flash = 0
        self.notifier = Notifier(self._on_notify_action)

    # ---- helper de filas ----
    def rows(self):
        return sorted(self.cfg["reminders"], key=lambda r: r["target"])

    # ---- ciclo de vida ----
    def do_activate(self):
        print("[rec] activate: creando ventana...", flush=True)
        if self.win:
            self.win.present()
            return
        h = int(self.cfg.get("height", DEFAULT_H))
        w = int(h * ASPECT)
        self.win = WB.make_window(
            self, "recordatorio",
            "Recordatorio Dorado" + (" [DEBUG]" if DEBUG else ""),
            w, h, self.cfg, DEBUG,
        )
        WB.install_css("recordatorio", DEBUG, extra=CSS_BTN)

        self.image = WB.make_picture(w, h)
        overlay = Gtk.Overlay()
        overlay.set_child(self.image)

        self.btn_add = self._make_rec_button(i18n._("New reminder…"))
        self.btn_add.connect("clicked", self._on_add_clicked)
        overlay.add_overlay(self.btn_add)

        self.win.set_child(overlay)

        drag = WB.wire_drag(self.image, self.win, lambda: self.cfg.get("locked"))
        drag.connect("drag-end", self.on_drag_end)
        WB.wire_click(self.image, 3, self.on_right_click)
        WB.wire_click(self.image, 1, self.on_left_click)
        WB.wire_keys(self.win, self.on_key)
        self.win.connect("notify::scale-factor", lambda *_: self.refresh())

        self.win.present()
        print(f"[rec] ventana presentada ({w}x{h}).", flush=True)
        self._hand_overdue()
        self._layout_buttons()
        self.refresh()
        self.restart_timer()

    def _hand_overdue(self):
        """Recordatorios vencidos con el widget cerrado: aviso y fuera."""
        now = now_epoch()
        missed = [r for r in self.cfg["reminders"] if r["target"] <= now]
        if not missed:
            return
        for r in missed:
            body = r["note"] or i18n._("reminder")
            self.notifier.notify(
                i18n._("Golden Reminder"),
                i18n._("Missed while the widget was off: {note}", note=body),
            )
            print(f"[rec] vencido sin aviso: {r['note']} ({r['target']})", flush=True)
        self.cfg["reminders"] = [r for r in self.cfg["reminders"] if r["target"] > now]
        save_config(self.cfg)

    # ---- render ----
    def refresh(self):
        if self.image is None:
            return
        h = int(self.cfg.get("height", DEFAULT_H))
        w = int(h * ASPECT)
        locked = bool(self.cfg.get("locked", False))
        scale = WB.widget_scale(self.win)
        try:
            tex = render_texture(w, h, self.rows(), now_epoch(),
                                 locked, self._flash, scale=scale)
            self.image.set_paintable(tex)
            self.image.set_size_request(w, h)
        except Exception as e:
            print(f"[rec] ERROR render: {e}", file=sys.stderr, flush=True)

    def restart_timer(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        self._timer_id = GLib.timeout_add(1000, self.on_tick)

    def on_tick(self):
        try:
            self._flash += 1
            self._check_expired()
            self.refresh()
        except Exception as e:
            print(f"[rec] tick: {e}", file=sys.stderr)
        return True

    def _check_expired(self):
        now = now_epoch()
        for rem in self.cfg["reminders"]:
            if rem["target"] <= now and rem["id"] not in self._fired:
                self._fired.add(rem["id"])
                body = rem["note"] or i18n._("reminder")
                print(f"[rec] ¡suena!: {body}", flush=True)
                if self.cfg.get("sound", True):
                    play_tone()
                self.notifier.notify(
                    i18n._("Reminder: {note}", note=body),
                    i18n._("time's up!"),
                    actions=[("snooze", i18n._("Snooze 5 min"))],
                    uid=rem["id"],
                )

    def _on_notify_action(self, nid, action):
        if action == "snooze":
            uid = self.notifier.nid_to_uid.get(nid)
            self.act_snooze(uid)

    # ---- botones overlay ----
    @staticmethod
    def _make_rec_button(tooltip):
        b = Gtk.Button(label="")
        b.add_css_class("flat")
        b.add_css_class("rec")
        b.set_tooltip_text(tooltip)
        b.set_focusable(False)
        b.set_focus_on_click(False)
        try:
            b.set_cursor_from_name("pointer")
        except Exception:
            pass
        return b

    def _layout_buttons(self):
        if self.btn_add is None:
            return
        h = int(self.cfg.get("height", DEFAULT_H))
        w = int(h * ASPECT)
        rows = self.rows()
        zones = recordatorio_button_zones(w, h, rows)
        locked = bool(self.cfg.get("locked", False))
        self._place(self.btn_add, zones["add"])
        # recrear las ✕ solo si cambia el numero de filas visibles
        ndel = sum(1 for k in zones if k.startswith("del"))
        while len(self.btn_del) > ndel:
            btn = self.btn_del.pop()
            btn.unparent()
        while len(self.btn_del) < ndel:
            btn = self._make_rec_button(i18n._("Delete reminder"))
            btn._idx = 0
            btn.connect("clicked", self._on_del_clicked)
            self.btn_del.append(btn)
            self.image.get_parent().add_overlay(btn)
        for i, btn in enumerate(self.btn_del):
            btn._idx = i
            zone = zones.get(f"del{i}")
            if zone:
                self._place(btn, zone)
        for btn in [self.btn_add, *self.btn_del]:
            btn.set_sensitive(not locked)
        # tooltip dinamico del '+'
        self.btn_add.set_tooltip_text(i18n._("New reminder…"))

    def _place(self, btn, zone):
        cx, cy, r = zone
        side = int(r * 2)
        btn.set_size_request(side, side)
        btn.set_margin_start(int(cx - r))
        btn.set_margin_top(int(cy - r))
        btn.set_margin_end(0)
        btn.set_margin_bottom(0)

    # ---- alta de recordatorio ----
    def add_dialog(self):
        if self.win is None or self.cfg.get("locked"):
            return
        dlg = Gtk.Dialog(title=i18n._("New reminder…"), transient_for=self.win,
                         modal=True)
        dlg.add_button(i18n._("Cancel"), Gtk.ResponseType.CANCEL)
        dlg.add_button(i18n._("Add"), Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(
            column_spacing=12, row_spacing=12,
            margin_top=14, margin_bottom=14, margin_start=14, margin_end=14)
        dlg.get_content_area().append(grid)

        grid.attach(Gtk.Label(label=i18n._("Note"), halign=Gtk.Align.START), 0, 0, 1, 1)
        note = Gtk.Entry(hexpand=True, max_length=MAX_NOTE)
        grid.attach(note, 1, 0, 2, 1)

        r_min = Gtk.CheckButton(active=True, label=i18n._("In minutes"))
        grid.attach(r_min, 0, 1, 1, 1)
        spin = Gtk.SpinButton.new(Gtk.Adjustment.new(10, 1, 1440, 1, 10, 0), 1, 0)
        grid.attach(spin, 1, 1, 2, 1)

        r_time = Gtk.CheckButton(label=i18n._("At time"))
        r_min.set_group(r_time)
        grid.attach(r_time, 0, 2, 1, 1)
        hhmm = Gtk.Entry(hexpand=True, max_length=5)
        hhmm.set_placeholder_text("HH:MM")
        grid.attach(hhmm, 1, 2, 2, 1)

        def on_radio(_b):
            spin.set_sensitive(r_min.get_active())
            hhmm.set_sensitive(r_time.get_active())
        r_min.connect("toggled", on_radio)
        r_time.connect("toggled", on_radio)

        hint = Gtk.Label(halign=Gtk.Align.START)
        grid.attach(hint, 0, 3, 3, 1)

        def on_response(_dlg, resp):
            if resp == Gtk.ResponseType.OK:
                err = None
                if r_min.get_active():
                    target = now_epoch() + int(spin.get_value()) * 60
                else:
                    target = parse_hhmm(hhmm.get_text())
                    err = None if target is not None else i18n._(
                        "Invalid time (HH:MM 24 h)")
                if target is None:
                    hint.set_text(err or "")
                    return
                note_txt = (note.get_text() or "").strip()[:MAX_NOTE]
                self.add_reminder(note_txt, int(target))
            _dlg.destroy()

        dlg.connect("response", on_response)
        dlg.present()

    def add_reminder(self, note_txt, target, created=None):
        if created is None:
            created = time.time()
        rem = {
            "note": note_txt[:MAX_NOTE],
            "target": int(target),
            "created": int(created),
            "id": f"{time.time_ns():x}",
        }
        self.cfg["reminders"].append(rem)
        save_config(self.cfg)
        print(f"[rec] + '{note_txt}' -> {target} "
              f"({format_countdown(target - now_epoch())})", flush=True)
        self._layout_buttons()
        self.refresh()

    def _on_add_clicked(self, _btn):
        self.act_add()

    def _on_del_clicked(self, btn):
        if self.cfg.get("locked"):
            return
        idx = getattr(btn, "_idx", 0)
        self.act_del(idx)

    def act_add(self, *_):
        self.add_dialog()

    def act_del(self, idx):
        rows = self.rows()
        if idx < 0 or idx >= len(rows):
            return
        uid = rows[idx]["id"]
        self.cfg["reminders"] = [r for r in self.cfg["reminders"] if r["id"] != uid]
        save_config(self.cfg)
        print(f"[rec] - fila {idx}", flush=True)
        self._layout_buttons()
        self.refresh()

    def act_snooze(self, uid):
        if uid is None:
            return
        for rem in self.cfg["reminders"]:
            if rem["id"] == uid:
                target = int(now_epoch()) + SNOOZE_S
                rem["target"] = target
                rem["created"] = target - SNOOZE_S
                self._fired.discard(uid)
                print(f"[rec] posponer '{rem['note']}' +{SNOOZE_S}s", flush=True)
        save_config(self.cfg)
        self._layout_buttons()
        self.refresh()

    def act_clear_fired(self, *_):
        """Quita los recordatorios ya vencidos (filas en destello)."""
        now = now_epoch()
        before = len(self.cfg["reminders"])
        self.cfg["reminders"] = [
            r for r in self.cfg["reminders"] if r["target"] > now]
        save_config(self.cfg)
        if len(self.cfg["reminders"]) != before:
            print(f"[rec] limpiados {before - len(self.cfg['reminders'])} avisos", flush=True)
        self._layout_buttons()
        self.refresh()

    def toggle_sound(self, *_):
        cfg = self.cfg
        cfg["sound"] = not bool(cfg.get("sound", True))
        save_config(cfg)
        print(f"[rec] sonido={'on' if cfg['sound'] else 'off'}", flush=True)

    # ---- interaccion ----
    def _save_position(self):
        WB.store_position(self.win, self.cfg, CONFIG_PATH)

    def on_drag_end(self, _gesture, _ox, _oy):
        self._save_position()

    def on_left_click(self, _gesture, n_press, _x, _y):
        if n_press == 2:
            WB.toggle_locked(self.cfg, CONFIG_PATH)
            self._layout_buttons()
            self.refresh()
            print(f"[rec] {'bloqueado' if self.cfg.get('locked') else 'desbloqueado'}", flush=True)

    def on_right_click(self, _gesture, n_press, x, y):
        if n_press != 1 or self.cfg.get("locked"):
            return
        has_fired = any(r["target"] <= now_epoch() for r in self.cfg["reminders"])
        entries = [
            (i18n._("New reminder…"), "add", self.act_add),
            (i18n._("Sound ✓") if self.cfg.get("sound", True)
             else i18n._("Sound ✗"), "sound", self.toggle_sound),
        ]
        if has_fired:
            entries.append((i18n._("Clear alerts"), "clearfired", self.act_clear_fired))
        entries += [
            (i18n._("Lock clicks ✓") if self.cfg.get("locked")
             else i18n._("Lock clicks"), "lock", self.act_lock),
            (i18n._("Size +"), "bigger", self.act_bigger),
            (i18n._("Size −"), "smaller", self.act_smaller),
            (i18n._("Settings…"), "settings", self.act_settings),
            (i18n._("Quit"), "quit", self.act_quit),
        ]
        WB.popup_menu(self.image, x, y, self, entries)

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
            return True
        if nl == "a" and not self.cfg.get("locked"):
            self.add_dialog()
            return True
        if nl == "s":
            self.toggle_sound()
            return True
        if WB.is_bigger_key(name):
            self.resize_by(40)
            return True
        if WB.is_smaller_key(name):
            self.resize_by(-40)
            return True
        return False

    # ---- acciones ----
    def act_lock(self, *_):
        WB.toggle_locked(self.cfg, CONFIG_PATH)
        self._layout_buttons()
        self.refresh()

    def act_bigger(self, *_):
        self.resize_by(40)

    def act_smaller(self, *_):
        self.resize_by(-40)

    def act_settings(self, *_):
        WB.settings_dialog(self.win, self.cfg, [
            ("height", "Height", "spin", (MIN_H, MAX_H, 10, 0)),
            ("opacity", "Opacity", "spin", (0.1, 1.0, 0.05, 2)),
            ("sound", "Sound on", "switch", None),
        ], self.apply_settings)

    def apply_settings(self, cfg):
        save_config(cfg)
        try:
            self.win.set_opacity(float(cfg.get("opacity", 1.0)))
        except (TypeError, ValueError):
            pass
        h = int(cfg.get("height", DEFAULT_H))
        self.cfg["height"] = h
        self.win.set_default_size(int(h * ASPECT), h)
        self._layout_buttons()
        self.refresh()

    def act_quit(self, *_):
        self.quit()

    def resize_by(self, delta):
        h = max(MIN_H, min(MAX_H, int(self.cfg.get("height", DEFAULT_H)) + delta))
        self.cfg["height"] = h
        save_config(self.cfg)
        self.win.set_default_size(int(h * ASPECT), h)
        self.refresh()
        self._layout_buttons()
        self._save_position()


def main():
    app = ReminderWidget()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
