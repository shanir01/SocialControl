#!/usr/bin/env bash
# Sirf server + phone dashboard (bina desktop app) — Linux/Mac/Termux
cd "$(dirname "$0")/../backend" && python3 -m socialcontrol serve --port "${SC_PORT:-8765}"
