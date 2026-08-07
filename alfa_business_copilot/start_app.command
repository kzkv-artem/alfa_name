#!/bin/bash
cd "$(dirname "$0")"
./.venv/bin/python "main.py"
echo
echo "Окно можно закрыть."
read -n 1 -s
