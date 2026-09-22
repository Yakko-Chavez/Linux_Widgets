// Preferencias de desktop-widgets@yakko-chavez.github.io.
// Solo Gtk/Adw/Gio: prohibido importar librerias de GNOME Shell aqui.

import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import { ExtensionPreferences } from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

const TITLES_ES = {
    'launch-reloj': 'Reloj Diver',
    'launch-agenda': 'Agenda de Lujo',
    'launch-clima': 'Clima Dorado',
    'launch-sysmon': 'Monitor Dorado',
    'launch-chrono': 'Cronógrafo Mecánico',
    'launch-calc': 'Calculadora Dorada',
    group: 'Widgets a lanzar al activar la extensión',
};

const TITLES_EN = {
    'launch-reloj': 'Dive watch',
    'launch-agenda': 'Luxury agenda',
    'launch-clima': 'Weather',
    'launch-sysmon': 'System monitor',
    'launch-chrono': 'Chronograph',
    'launch-calc': 'Calculator',
    group: 'Widgets to launch when the extension is enabled',
};

export default class DesktopWidgetsPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const lang = (GLib.get_language_names()[0] || 'en').startsWith('es')
            ? TITLES_ES : TITLES_EN;
        const settings = this.getSettings('org.gnome.shell.extensions.desktop-widgets');

        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({ title: lang.group });
        for (const [key, title] of [
            ['launch-reloj', lang['launch-reloj']],
            ['launch-agenda', lang['launch-agenda']],
            ['launch-clima', lang['launch-clima']],
            ['launch-sysmon', lang['launch-sysmon']],
            ['launch-chrono', lang['launch-chrono']],
            ['launch-calc', lang['launch-calc']],
        ]) {
            const row = new Adw.SwitchRow({ title });
            settings.bind(key, row, 'active', Gio.SettingsBindFlags.DEFAULT);
            group.add(row);
        }
        page.add(group);
        window.add(page);
    }
}
