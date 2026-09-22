#!/bin/bash
# Lanzador del widget Reloj Diver
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/reloj_widget.py" "$@"
