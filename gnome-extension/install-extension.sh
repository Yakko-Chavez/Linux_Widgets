#!/bin/bash
# Instala/actualiza la extension desktop-widgets@yakko-chavez.github.io
# (nivel usuario) con los widgets incluidos, y la activa.
set -euo pipefail

UUID="desktop-widgets@yakko-chavez.github.io"
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$DIR")"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"

mkdir -p "$DEST/widgets" "$DEST/schemas"
cp "$DIR/$UUID/metadata.json" "$DIR/$UUID/extension.js" "$DIR/$UUID/LICENSE" \
   "$DIR/$UUID/prefs.js" "$DEST/"
cp "$DIR/$UUID/schemas/org.gnome.shell.extensions.desktop-widgets.gschema.xml" \
   "$DEST/schemas/"
glib-compile-schemas "$DEST/schemas"

WIDGETS_SRC=(
  i18n.py
  widget_base.py
  reloj_widget.py reloj_draw.py
  agenda_widget.py agenda_draw.py
  clima_widget.py clima_draw.py
  sysmon_widget.py sysmon_draw.py
  chrono_widget.py chrono_draw.py
  calc_widget.py calc_draw.py
  recordatorio_widget.py recordatorio_draw.py
)
EXAMPLES=(
  config.example.json agenda_config.example.json clima_config.example.json
  sysmon_config.example.json chrono_config.example.json
  calc_config.example.json recordatorio_config.example.json
)
for f in "${WIDGETS_SRC[@]}" "${EXAMPLES[@]}"; do
  cp "$REPO/$f" "$DEST/widgets/"
done

echo "Copiada a $DEST"
if gnome-extensions enable "$UUID"; then
  echo "Extension activada: al arrancar lanza sola los widgets que falten."
else
  echo "No se pudo activar en caliente: cierra sesion y entra de nuevo, luego:"
  echo "  gnome-extensions enable $UUID"
fi
