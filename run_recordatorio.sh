#!/bin/bash
# Lanzador del widget Recordatorio Dorado
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/recordatorio_widget.py" "$@"
