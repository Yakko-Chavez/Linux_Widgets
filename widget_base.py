#!/usr/bin/env python3
"""Infraestructura comun de los widgets de escritorio (Wayland + GNOME).

Centraliza lo que los 4 widgets repetian:
- Carga/guardado de config JSON con sanitizado de rangos (tamano, opacidad, x/y).
- Render offscreen pycairo -> Gdk.MemoryTexture (sin archivos, sin gi-cairo).
- Creacion de ventana transparente sin decoracion + Gtk.Picture.
- Arrastre Wayland (begin_move), click derecho/izquierdo, teclas.
- Menu contextual (Gio.Menu + Gtk.PopoverMenu).
- (Des)bloqueo de clicks.

Notas Wayland/GNOME verificadas (GTK 4.22):
- Gtk.Window NO tiene .move(): el compositor decide la posicion. restore_position()
  lo intenta de forma segura y no rompe si la API no existe.
- Gdk.Toplevel NO expone get_position_x/y: store_position() es best-effort y un
  no-op silencioso en Wayland (no finge guardar lo que no puede leer).
- Gtk.Widget.set_opacity() SI existe en GTK4 y es la via valida.
"""

import json
import os
import shutil
import sys

import cairo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

APP_FLAGS = (
    Gio.ApplicationFlags.ALLOW_REPLACEMENT | Gio.ApplicationFlags.REPLACE
)

SCALE = 2  # Nitidez HiDPI cuando el monitor es x2; ver widget_scale().


def widget_scale(win):
    """Factor de escala real del monitor (1 en 1080p, 2 en HiDPI...).

    El buffer Cairo debe dibujarse a tamano_logico x escala: asi el
    Gtk.Picture mide tamano_logico y la ventana NO crece al doble en
    pantallas x1 (lo que ademas desalineaba los botones overlay).
    Sin superficie aun (antes de present) devuelve 1.
    """
    try:
        s = win.get_scale_factor() if win is not None else 1
        if isinstance(s, int) and s >= 1:
            return s
    except Exception:
        pass
    return 1


# ---- config ----

def config_path(filename):
    """Ruta de config por usuario: ~/.config/desktop-widgets/<filename>.

    Al primer arranque la siembra desde una config previa junto al script
    (repo local) o desde su *.example.json (instalacion via extension), de
    modo que cada usuario tenga la suya sin escribir en el codigo fuente.
    """
    user_path = os.path.join(
        GLib.get_user_config_dir(), "desktop-widgets", filename)
    if os.path.exists(user_path):
        return user_path
    try:
        os.makedirs(os.path.dirname(user_path), exist_ok=True)
        here = os.path.dirname(os.path.abspath(__file__))
        stem, ext = os.path.splitext(filename)
        for src in (os.path.join(here, filename),
                    os.path.join(here, f"{stem}.example{ext}")):
            if os.path.isfile(src):
                shutil.copyfile(src, user_path)
                break
    except OSError as e:
        print(f"No se pudo preparar config de usuario: {e}", file=sys.stderr)
    return user_path


def load_config(path, defaults, int_ranges=None, float_ranges=None):
    """Carga JSON sobre defaults y sanitiza rangos.

    int_ranges/float_ranges: {clave: (min, max, fallback)}.
    Ademas: elimina la clave legacy 'always_on_top' (Wayland no permite
    keep-above desde la app) y normaliza opacity/x/y.
    """
    cfg = dict(defaults)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    cfg.pop("always_on_top", None)
    for key, (lo, hi, fallback) in (int_ranges or {}).items():
        try:
            cfg[key] = max(lo, min(hi, int(cfg.get(key, fallback))))
        except (TypeError, ValueError):
            cfg[key] = fallback
    for key, (lo, hi, fallback) in (float_ranges or {}).items():
        try:
            cfg[key] = max(lo, min(hi, float(cfg.get(key, fallback))))
        except (TypeError, ValueError):
            cfg[key] = fallback
    try:
        cfg["opacity"] = max(0.1, min(1.0, float(cfg.get("opacity", 1.0))))
    except (TypeError, ValueError):
        cfg["opacity"] = 1.0
    for key in ("x", "y"):
        if key in cfg:
            try:
                cfg[key] = int(cfg[key])
            except (TypeError, ValueError):
                cfg[key] = -1
    return cfg


def save_config(path, cfg):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"No se pudo guardar config: {e}", file=sys.stderr)


# ---- render ----

def settings_dialog(parent, cfg, specs, on_save):
    """Dialogo de configuracion generico (GTK4, respuesta por senal).

    specs: [(clave, etiqueta, tipo, extra)] con tipo:
      - "spin":   extra = (min, max, step, digits); digits=0 -> valor int
      - "switch": extra = None
      - "entry":  extra = None
    Al aceptar vuelca los valores en cfg y llama on_save(cfg): ahi cada
    widget guarda su config y se refresca. Etiquetas via i18n.
    """
    import i18n

    dlg = Gtk.Dialog(title=i18n._("Settings"), transient_for=parent, modal=True)
    dlg.add_button(i18n._("Cancel"), Gtk.ResponseType.CANCEL)
    dlg.add_button(i18n._("Apply"), Gtk.ResponseType.OK)
    dlg.set_default_response(Gtk.ResponseType.OK)

    grid = Gtk.Grid(
        column_spacing=14, row_spacing=12,
        margin_top=14, margin_bottom=14, margin_start=14, margin_end=14)
    dlg.get_content_area().append(grid)

    controls = {}
    for row, (key, label, kind, extra) in enumerate(specs):
        grid.attach(Gtk.Label(
            label=i18n._(label), halign=Gtk.Align.START, hexpand=True,
            margin_start=6), 0, row, 1, 1)
        if kind == "spin":
            lo, hi, step, digits = extra
            ctrl = Gtk.SpinButton.new(
                Gtk.Adjustment.new(float(cfg.get(key, lo)), lo, hi, step,
                                   step * 10, 0),
                1, digits)
            ctrl.set_value(float(cfg.get(key, lo)))
        elif kind == "switch":
            ctrl = Gtk.Switch(active=bool(cfg.get(key)))
            ctrl.set_halign(Gtk.Align.END)
        else:  # entry
            ctrl = Gtk.Entry()
            ctrl.set_text(str(cfg.get(key, "")))
            ctrl.set_width_chars(16)
            ctrl.set_halign(Gtk.Align.END)
        controls[key] = (kind, extra, ctrl)
        grid.attach(ctrl, 1, row, 1, 1)

    def _on_response(_dlg, resp):
        if resp == Gtk.ResponseType.OK:
            for key, (kind, _extra, ctrl) in controls.items():
                if kind == "spin":
                    _lo, _hi, _step, digits = _extra
                    value = ctrl.get_value()
                    cfg[key] = int(value) if digits == 0 else round(float(value), digits)
                elif kind == "switch":
                    cfg[key] = bool(ctrl.get_active())
                else:
                    cfg[key] = ctrl.get_text().strip()
            try:
                on_save(cfg)
            except Exception as e:
                print(f"settings: {e}", file=sys.stderr)
        _dlg.destroy()

    dlg.connect("response", _on_response)
    dlg.present()


def render_texture(width, height, paint, scale=SCALE):
    """Dibuja con paint(cr) en un buffer x escala y devuelve Gdk.MemoryTexture.

    paint() dibuja en coords LOGICAS (la base ya aplica cr.scale). Pasar
    scale=widget_scale(win) para que la ventana mida lo que dice la config
    en cualquier monitor.
    """
    scale = scale if isinstance(scale, int) and scale >= 1 else SCALE
    px_w, px_h = int(width * scale), int(height * scale)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, px_w, px_h)
    cr = cairo.Context(surf)
    cr.scale(scale, scale)
    paint(cr)
    surf.flush()
    data = GLib.Bytes.new(bytes(surf.get_data()))
    return Gdk.MemoryTexture.new(
        px_w, px_h, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, data,
        surf.get_stride(),
    )


# ---- ventana ----

def _css(css_class, debug):
    if debug:
        return (
            f"window.{css_class} {{ background-color: rgba(40,40,40,1); "
            f"border: 4px solid gold; }}\n"
            f"window.{css_class} picture {{ background-color: "
            f"rgba(40,40,40,1); }}\n"
        )
    return (
        f"window.{css_class} {{ background-color: transparent; }}\n"
        f"window.{css_class} picture {{ background-color: transparent; }}\n"
    )


def install_css(css_class, debug, extra="", debug_css=None):
    if debug and debug_css is not None:
        css = debug_css
    else:
        css = _css(css_class, debug) + extra
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode())
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def restore_position(win, cfg):
    """Restaura x,y guardados. Seguro en GTK4/Wayland: si .move no existe
    (caso normal) no hace nada en vez de romper el arranque."""
    x, y = cfg.get("x", -1), cfg.get("y", -1)
    if not (isinstance(x, int) and isinstance(y, int) and x >= 0 and y >= 0):
        return False
    try:
        win.move(x, y)  # no existe en GTK4 -> AttributeError -> ignorar
        return True
    except (AttributeError, TypeError):
        return False


def store_position(win, cfg, path):
    """Best-effort: en Wayland GDK no expone la posicion de la ventana,
    asi que normalmente es un no-op silencioso (devuelve False)."""
    try:
        surf = win.get_surface()
        get_x = getattr(surf, "get_position_x", None)
        get_y = getattr(surf, "get_position_y", None)
        if get_x is None or get_y is None:
            return False
        cfg["x"] = get_x()
        cfg["y"] = get_y()
        save_config(path, cfg)
        return True
    except Exception:
        return False


def make_window(app, css_class, title, width, height, cfg, debug):
    win = Gtk.Window(application=app)
    win.add_css_class(css_class)
    win.set_title(title)
    win.set_decorated(bool(debug))
    win.set_resizable(False)
    win.set_focus_on_click(False)
    win.set_default_size(width, height)
    restore_position(win, cfg)
    try:
        win.set_opacity(float(cfg.get("opacity", 1.0)))
    except (TypeError, ValueError):
        pass
    return win


def make_picture(width, height):
    image = Gtk.Picture()
    image.set_content_fit(Gtk.ContentFit.FILL)
    image.set_can_shrink(False)
    image.set_size_request(width, height)
    image.set_can_target(True)
    return image


# ---- interaccion ----

def wire_drag(image, win, is_locked):
    """Arrastre con boton izquierdo via protocolo Wayland. Devuelve el gesto
    para que la app conecte 'drag-end' si quiere (p. ej. guardar posicion)."""
    drag = Gtk.GestureDrag.new()
    drag.set_button(1)

    def on_begin(gesture, x, y):
        if is_locked():
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        try:
            surf = win.get_surface()
            surf.begin_move(
                gesture.get_current_event_device(),
                gesture.get_current_button(),
                x, y,
                gesture.get_current_event_time(),
            )
        except Exception as e:
            print(f"Move: usa Super+arrastrar en GNOME ({e})", file=sys.stderr)

    drag.connect("drag-begin", on_begin)
    image.add_controller(drag)
    return drag


def wire_click(image, button, handler):
    """Click de raton (3 = derecho, 1 = izquierdo/doble). Firma GTK4:
    handler(gesture, n_press, x, y)."""
    click = Gtk.GestureClick.new()
    click.set_button(button)
    click.connect("pressed", handler)
    image.add_controller(click)
    return click


def wire_keys(win, handler):
    keys = Gtk.EventControllerKey.new()
    keys.connect("key-pressed", handler)
    win.add_controller(keys)
    return keys


def popup_menu(parent, x, y, app, entries):
    """Menu contextual. entries = [(etiqueta, nombre_accion, callback)]."""
    menu = Gio.Menu()
    for label, name, _cb in entries:
        menu.append(label, f"app.{name}")
    for _label, name, cb in entries:
        if app.lookup_action(name) is None:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            app.add_action(action)
    pop = Gtk.PopoverMenu.new_from_model(menu)
    pop.set_parent(parent)
    pop.set_pointing_to(Gdk.Rectangle(int(x), int(y), 1, 1))
    pop.popup()
    return pop


# ---- teclas comunes ----

def is_quit_key(name, nl):
    return nl in ("q", "escape")


def is_lock_key(nl):
    return nl == "l"


def is_bigger_key(name):
    return name in ("plus", "KP_Add", "equal")


def is_smaller_key(name):
    return name in ("minus", "KP_Subtract")


def toggle_locked(cfg, path):
    cfg["locked"] = not cfg.get("locked", False)
    save_config(path, cfg)
    return cfg["locked"]


def app_dir():
    """Directorio del script que importa este modulo (no el de la base)."""
    try:
        import inspect

        for frame in inspect.stack():
            fname = frame.filename
            if os.path.basename(fname) != "widget_base.py" and fname.endswith(".py"):
                return os.path.dirname(os.path.abspath(fname))
    except Exception:
        pass
    return os.getcwd()
