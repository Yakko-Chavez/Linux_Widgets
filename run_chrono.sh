#!/bin/bash
# Lanzador del widget Cronografo Mecanico
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/chrono_widget.py" "$@"
