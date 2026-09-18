#!/bin/bash
# Instala/actualiza la extension rolex-below@local y la activa.
set -u
SRC="$(cd "$(dirname "$0")" && pwd)/rolex-below@local"
DEST="$HOME/.local/share/gnome-shell/extensions/rolex-below@local"
mkdir -p "$DEST"
cp "$SRC/extension.js" "$SRC/metadata.json" "$DEST/"
echo "Copiada a $DEST"
if gnome-extensions enable rolex-below@local; then
  echo "Extension activada."
else
  echo "No se pudo activar en caliente: cierra sesion y entra de nuevo, luego:"
  echo "  gnome-extensions enable rolex-below@local"
fi
