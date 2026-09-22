#!/bin/bash
# Lanzador del widget Calculadora Dorada
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/calc_widget.py" "$@"
