#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "$0")"
exec python3 ./strop_keyboard.py "$@"
