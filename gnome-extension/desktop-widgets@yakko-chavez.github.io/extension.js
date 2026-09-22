// desktop-widgets@yakko-chavez.github.io — Widgets de escritorio:
// lanzador + fondo + memoria de posicion.
//
// - Al activarse lanza los 5 widgets Python (GTK4) que viajan dentro de la
//   extension en widgets/. Solo lanza los que NO esten ya corriendo: si el
//   usuario los arranca por su cuenta (autostart o lanzadores), simplemente
//   los adopta.
// - Los mantiene al fondo de la pila (lower) y visibles en todos los
//   escritorios (stick).
// - Recuerda la ultima posicion de cada widget y la restaura al abrirlo.
//   En Wayland la app no puede posicionarse sola (Gtk.Window no tiene .move
//   y GDK no expone la posicion): lo hace el compositor desde aqui.
//
// Sobre los scripts externos: las ventanas de escritorio GTK4 no pueden
// crearse dentro del proceso de gnome-shell (importar Gtk/Gdk ahi esta
// prohibido), por eso los widgets son procesos Python aparte, distribuidos
// bajo licencia MIT (ver LICENSE) y sin binarios. Los procesos se lanzan en
// enable(), se terminan en disable() y salen limpios. Las dependencias de
// sistema (python3-gi, gir1.2-gtk-4.0, python3-cairo) no se instalan nunca
// automaticamente: si falta python3 se notifica con las instrucciones.
//
// Estado: ~/.config/desktop-widgets/positions.json  { clave: {x, y, w, h} }
// Clave: el app-id (com.vibes.*) o el titulo si es instancia --debug.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

// app-id -> script relativo a <extension>/widgets/ + clave GSettings
const WIDGETS = [
    { appId: 'com.vibes.reloj-widget', script: 'reloj_widget.py', setting: 'launch-reloj' },
    { appId: 'com.vibes.agenda-widget', script: 'agenda_widget.py', setting: 'launch-agenda' },
    { appId: 'com.vibes.clima-widget', script: 'clima_widget.py', setting: 'launch-clima' },
    { appId: 'com.vibes.sysmon-widget', script: 'sysmon_widget.py', setting: 'launch-sysmon' },
    { appId: 'com.vibes.chrono-widget', script: 'chrono_widget.py', setting: 'launch-chrono' },
    { appId: 'com.vibes.calc-widget', script: 'calc_widget.py', setting: 'launch-calc' },
];

const SCHEMA_ID = 'org.gnome.shell.extensions.desktop-widgets';

const APP_IDS = WIDGETS.map(w => w.appId);

const TITLES = [
    'Reloj Diver',
    'Agenda de Lujo',
    'Clima Dorado',
    'Monitor Dorado',
    'Cronógrafo Mecánico',
    'Calculadora Dorada',
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
        this._pending = new Set(); // ventanas esperando app-id/titulo
        this._procs = [];          // Gio.Subprocess de los widgets lanzados
        try {
            // getSettings() monta el origen de schemas desde el dir de la
            // extension; new Gio.Settings() solo miraria el sistema.
            this._settings = this.getSettings(SCHEMA_ID);
        } catch (e) {
            log(`[desktop-widgets] schema ${SCHEMA_ID} no disponible: ${e}`);
            this._settings = null;
        }
        this._createdId = global.display.connect(
            'window-created', (_display, win) => this._adopt(win));
        // Ventanas que ya existian al activar la extension.
        for (const actor of global.get_window_actors()) {
            try {
                const win = actor.get_meta_window();
                if (win)
                    this._adopt(win);
            } catch (e) {
                log(`[desktop-widgets] actor inicial: ${e}`);
            }
        }
        this._launchWidgets();
        log('[desktop-widgets] activada');
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
                if (rec && rec.applyId)
                    GLib.source_remove(rec.applyId);
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
        if (this._pending) {
            for (const win of this._pending) {
                try {
                    win.disconnectObject(this);
                } catch (e) { /* ventana ya destruida */ }
            }
            this._pending.clear();
        }
        // Terminar los procesos que esta extension lanzo. Los widgets que el
        // usuario arranco por su cuenta siguen corriendo (no son nuestros).
        if (this._procs) {
            for (const proc of this._procs) {
                try {
                    proc.force_exit();
                } catch (e) { /* ya salio */ }
            }
            this._procs = [];
        }
        this._flush();
        this._settings = null;
        log('[desktop-widgets] desactivada');
    }

    // ---- lanzador ----

    _launchWidgets() {
        const python = GLib.find_program_in_path('python3');
        if (!python) {
            // Bilingue: sin gettext, deteccion directa del idioma de sesion.
            const es = (GLib.get_language_names()[0] || 'en').startsWith('es');
            Main.notify('Desktop Widgets', es
                ? 'Se necesita python3 con PyGObject y GTK4: ' +
                  'sudo apt install python3-gi gir1.2-gtk-4.0 python3-cairo'
                : 'python3 with PyGObject and GTK4 is required: ' +
                  'sudo apt install python3-gi gir1.2-gtk-4.0 python3-cairo');
            return;
        }
        // App-ids ya en pantalla: no relanzar lo que el usuario abrio.
        const running = new Set();
        for (const actor of global.get_window_actors()) {
            try {
                const cls = actor.get_meta_window()?.get_wm_class();
                if (cls)
                    running.add(cls);
            } catch (e) { /* ventana efimera */ }
        }
        const widgetsDir = GLib.build_filenamev(
            [this.dir.get_path(), 'widgets']);
        for (const w of WIDGETS) {
            if (this._settings && !this._settings.get_boolean(w.setting))
                continue; // desactivado en las preferencias de la extension
            if (running.has(w.appId))
                continue;
            const script = GLib.build_filenamev([widgetsDir, w.script]);
            if (!Gio.File.new_for_path(script).query_exists(null)) {
                log(`[desktop-widgets] falta ${w.script}; reinstala la extension`);
                continue;
            }
            try {
                // Los widgets usan Gio.ApplicationFlags.REPLACE: si el mismo
                // widget arranca despues por lanzador, reemplaza este proceso
                // y la ventana nueva se adopta igual via window-created.
                this._procs.push(Gio.Subprocess.new(
                    [python, script], Gio.SubprocessFlags.NONE));
            } catch (e) {
                log(`[desktop-widgets] no se pudo lanzar ${w.script}: ${e}`);
            }
        }
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
        if (!key) {
            // En Wayland el app-id (wm_class) y el titulo llegan asincronos
            // despues de window-created: reintenta cuando mutter los actualice.
            if (this._pending.has(win))
                return;
            this._pending.add(win);
            win.connectObject(
                'notify::wm-class', () => this._retryAdopt(win),
                'notify::title', () => this._retryAdopt(win),
                'unmanaging', () => this._dropPending(win),
                this);
            return;
        }
        this._track(win, key);
    }

    _retryAdopt(win) {
        if (this._tracked.has(win))
            return;
        let key = null;
        try {
            key = this._keyFor(win);
        } catch (e) {
            return;
        }
        if (!key)
            return;
        this._dropPending(win);
        this._track(win, key);
    }

    _dropPending(win) {
        if (!this._pending.has(win))
            return;
        this._pending.delete(win);
        try {
            win.disconnectObject(this);
        } catch (e) { /* ya destruida */ }
    }

    _track(win, key) {
        this._tracked.set(win, { key, saveId: 0 });
        win.connectObject(
            'position-changed', () => this._scheduleSave(win),
            'size-changed', () => this._scheduleSave(win),
            'unmanaging', () => this._forget(win),
            this);
        // GNOME 50 elimino WindowActor 'map': aplica ahora y re-aplica
        // unos ciclos hasta que la ventana exista de verdad para mutter.
        this._apply(win);
        const rec = this._tracked.get(win);
        rec.tries = 0;
        rec.applyId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
            rec.applyId = 0;
            if (!this._tracked.has(win))
                return GLib.SOURCE_REMOVE;
            this._apply(win);
            rec.tries += 1;
            if (rec.tries >= 4)
                return GLib.SOURCE_REMOVE;
            return GLib.SOURCE_CONTINUE;
        });
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
                log(`[desktop-widgets] no se pudo mover ${rec.key}: ${e}`);
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
        if (rec && rec.applyId) {
            GLib.source_remove(rec.applyId);
            rec.applyId = 0;
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
            // make_directory_with_parents falla si ya existe: revisa antes.
            if (!dir.query_exists(null))
                dir.make_directory_with_parents(null);
            GLib.file_set_contents(
                statePath(), JSON.stringify(this._pos, null, 2));
        } catch (e) {
            log(`[desktop-widgets] no se pudo guardar estado: ${e}`);
        }
    }
}
