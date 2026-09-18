// rolex-below@local — Widgets de escritorio: fondo + memoria de posicion.
//
// - Mantiene los 5 widgets (Rolex, Agenda, Clima, Monitor, Cronografo) al
//   fondo de la pila (lower) y visibles en todos los escritorios (stick).
// - Recuerda la ultima posicion de cada widget y la restaura al abrirlo.
//   En Wayland la app no puede posicionarse sola (Gtk.Window no tiene .move
//   y GDK no expone la posicion): lo hace el compositor desde aqui.
//
// Estado: ~/.config/desktop-widgets/positions.json  { clave: {x, y, w, h} }
// Clave: el app-id (com.vibes.*) o el titulo si es instancia --debug.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Mainloop from 'resource:///org/gnome/shell/ui/mainloop.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

const APP_IDS = [
    'com.vibes.rolex-widget',
    'com.vibes.agenda-widget',
    'com.vibes.clima-widget',
    'com.vibes.sysmon-widget',
    'com.vibes.chrono-widget',
];

const TITLES = [
    'Rolex Submariner',
    'Agenda de Lujo',
    'Clima Dorado',
    'Monitor Dorado',
    'Cronógrafo Mecánico',
];

const SAVE_DELAY_MS = 800;

function statePath() {
    return GLib.build_filenamev(
        [GLib.get_user_config_dir(), 'desktop-widgets', 'positions.json']);
}

export default class WidgetsMemory extends Extension {
    enable() {
        this._pos = this._load();
        this._tracked = new Map(); // Meta.Window -> { key, saveId }
        this._createdId = global.display.connect(
            'window-created', (_display, win) => this._adopt(win));
        // Ventanas que ya existian al activar la extension.
        for (const actor of global.get_window_actors()) {
            try {
                const win = actor.get_meta_window();
                if (win)
                    this._adopt(win);
            } catch (e) {
                log(`[widgets-memory] actor inicial: ${e}`);
            }
        }
        log('[widgets-memory] activada');
    }

    disable() {
        if (this._createdId) {
            global.display.disconnect(this._createdId);
            this._createdId = 0;
        }
        if (this._tracked) {
            for (const [win] of this._tracked) {
                const rec = this._tracked.get(win);
                if (rec && rec.saveId)
                    GLib.source_remove(rec.saveId);
                try {
                    win.disconnectObject(this);
                } catch (e) { /* ventana ya destruida */ }
                try {
                    const actor = win.get_compositor_private();
                    if (actor)
                        actor.disconnectObject(this);
                } catch (e) { /* actor ya destruido */ }
            }
            this._tracked.clear();
        }
        this._flush();
        log('[widgets-memory] desactivada');
    }

    // ---- adopcion ----

    _keyFor(win) {
        let cls = '';
        try {
            cls = win.get_wm_class() || '';
        } catch (e) { /* sin wm-class */ }
        if (APP_IDS.includes(cls))
            return cls;
        let title = '';
        try {
            title = win.get_title() || '';
        } catch (e) { /* sin titulo */ }
        title = title.replace(/ \[DEBUG\]$/, '');
        if (TITLES.includes(title))
            return `title:${title}`;
        return null;
    }

    _adopt(win) {
        if (!win || this._tracked.has(win))
            return;
        let key = null;
        try {
            if (typeof win.is_override_redirect === 'function' &&
                win.is_override_redirect())
                return;
            key = this._keyFor(win);
        } catch (e) {
            return;
        }
        if (!key)
            return;
        this._tracked.set(win, { key, saveId: 0 });
        win.connectObject(
            'position-changed', () => this._scheduleSave(win),
            'size-changed', () => this._scheduleSave(win),
            'unmanaging', () => this._forget(win),
            this);
        const actor = win.get_compositor_private();
        if (actor && actor.mapped) {
            this._apply(win);
        } else if (actor) {
            // Cada vez que se mapea (apertura, desminimizar): fondo + posicion.
            actor.connectObject(
                'map', () => this._apply(win),
                this);
        } else {
            Mainloop.idle_add(() => {
                if (this._tracked.has(win))
                    this._apply(win);
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    _apply(win) {
        const rec = this._tracked.get(win);
        if (!rec)
            return;
        try {
            win.stick();
        } catch (e) { /* stick no disponible */ }
        const p = this._pos[rec.key];
        if (p && Number.isInteger(p.x) && Number.isInteger(p.y)) {
            try {
                const r = win.get_frame_rect();
                if (r.x !== p.x || r.y !== p.y)
                    win.move_frame(false, p.x, p.y);
            } catch (e) {
                log(`[widgets-memory] no se pudo mover ${rec.key}: ${e}`);
            }
        }
        try {
            win.lower();
        } catch (e) { /* lower no disponible */ }
    }

    // ---- memoria ----

    _scheduleSave(win) {
        const rec = this._tracked.get(win);
        if (!rec)
            return;
        if (rec.saveId)
            GLib.source_remove(rec.saveId);
        rec.saveId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT, SAVE_DELAY_MS, () => {
                rec.saveId = 0;
                this._capture(win);
                return GLib.SOURCE_REMOVE;
            });
    }

    _capture(win) {
        const rec = this._tracked.get(win);
        if (!rec)
            return;
        try {
            const r = win.get_frame_rect();
            this._pos[rec.key] = { x: r.x, y: r.y, w: r.width, h: r.height };
            this._flush();
        } catch (e) { /* ventana en transicion */ }
    }

    _forget(win) {
        // La ventana se cierra: guardar su ultima posicion y soltarla.
        this._capture(win);
        const rec = this._tracked.get(win);
        if (rec && rec.saveId) {
            GLib.source_remove(rec.saveId);
            rec.saveId = 0;
        }
        this._tracked.delete(win);
        try {
            win.disconnectObject(this);
        } catch (e) { /* ya destruida */ }
    }

    // ---- estado en disco ----

    _load() {
        try {
            const [ok, bytes] = GLib.file_get_contents(statePath());
            if (ok) {
                const data = JSON.parse(new TextDecoder().decode(bytes));
                if (data && typeof data === 'object')
                    return data;
            }
        } catch (e) { /* sin estado previo */ }
        return {};
    }

    _flush() {
        try {
            const dir = Gio.File.new_for_path(
                GLib.build_filenamev(
                    [GLib.get_user_config_dir(), 'desktop-widgets']));
            dir.make_directory_with_parents(null);
            GLib.file_set_contents(
                statePath(), JSON.stringify(this._pos, null, 2));
        } catch (e) {
            log(`[widgets-memory] no se pudo guardar estado: ${e}`);
        }
    }
}
