# Cross-platform recipes (macOS, Windows, Linux). Prefer `uv` for Python tooling.

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set shell := ["bash", "-cu"]

default:
    @just --list

# Initialise the local uv project (idempotent)
init:
    uv sync

# Generate synthetic long-format attendance CSV
synth:
    uv run python scripts/generate_synthetic_attendance.py

# Edit the Marimo notebook (opens browser)
edit:
    uv run marimo edit attendance_analyser_notebook.py

# Run the notebook as an app
run:
    uv run marimo run attendance_analyser_notebook.py

# Smoke-test analysis class methods without the UI
test:
    uv run python scripts/smoke_test.py

# Check notebook is valid Marimo Python
check:
    uv run marimo check attendance_analyser_notebook.py
