#!/bin/bash
cd "$(dirname "$0")"
./.venv/bin/python "otbor/try_risk_agent.py"
echo
echo "Окно можно закрыть."
read -n 1 -s
