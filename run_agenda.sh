#!/bin/bash
# Lanzador del widget Agenda de Lujo
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/agenda_widget.py" "$@"
