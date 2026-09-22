#!/bin/bash
# Empaqueta la extension para extensions.gnome.org:
# genera <uuid>.zip con metadata.json, extension.js, LICENSE y widgets/ en la
# RAIZ del zip (formato que exige EGO y gnome-extensions install).
set -euo pipefail

UUID="desktop-widgets@yakko-chavez.github.io"
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$DIR")"
OUT="$REPO/$UUID.zip"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/widgets"
cp "$DIR/$UUID/metadata.json" "$DIR/$UUID/extension.js" "$DIR/$UUID/LICENSE" \
   "$DIR/$UUID/prefs.js" "$STAGE/"

# Schema GSettings (el XML debe ir en el zip; EGO tambien espera el compilado)
mkdir -p "$STAGE/schemas"
cp "$DIR/$UUID/schemas/org.gnome.shell.extensions.desktop-widgets.gschema.xml" \
   "$STAGE/schemas/"
glib-compile-schemas "$STAGE/schemas"

# Widgets Python (fuentes en la raiz del repo: unica fuente de verdad)
WIDGETS_SRC=(
  i18n.py
  widget_base.py
  reloj_widget.py reloj_draw.py
  agenda_widget.py agenda_draw.py
  clima_widget.py clima_draw.py
  sysmon_widget.py sysmon_draw.py
  chrono_widget.py chrono_draw.py
  calc_widget.py calc_draw.py
)
EXAMPLES=(
  config.example.json agenda_config.example.json clima_config.example.json
  sysmon_config.example.json chrono_config.example.json
  calc_config.example.json
)
for f in "${WIDGETS_SRC[@]}" "${EXAMPLES[@]}"; do
  cp "$REPO/$f" "$STAGE/widgets/"
done

( cd "$STAGE" && zip -qr "$OUT" . )
echo "OK: $OUT"
