#!/bin/bash
# Lanzador del widget Monitor Dorado
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/sysmon_widget.py" "$@"
