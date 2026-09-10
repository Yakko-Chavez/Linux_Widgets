#!/bin/bash
# Lanzador del widget Clima Dorado (Puebla)
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/clima_widget.py" "$@"
