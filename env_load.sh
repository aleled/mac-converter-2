#!/bin/zsh
# Activate the Python virtual environment for this project
# Usage: source ./env_load.sh

if [ -d "venv" ]; then
    source venv/bin/activate
    echo "[INFO] Virtual environment activated."
else
    echo "[ERROR] No virtual environment found. Run 'python3 -m venv venv' first."
fi
