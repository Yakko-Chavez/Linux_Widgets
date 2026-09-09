#!/bin/bash
# Lanzador del widget Rolex Submariner
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/rolex_widget.py" "$@"
