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

# Edit the overview Marimo notebook (opens browser)
edit:
    uv run marimo edit overview_notebook.py

# Edit the pastoral care-pack notebook
edit-care:
    uv run marimo edit care_pack_notebook.py

# Run the overview notebook as an app
run:
    uv run marimo run overview_notebook.py

# Run the care-pack notebook as an app
run-care:
    uv run marimo run care_pack_notebook.py

# Smoke-test analysis class methods without the UI
test:
    uv run python scripts/smoke_test.py

# Check notebook is valid Marimo Python
check:
    uv run marimo check overview_notebook.py
    uv run marimo check care_pack_notebook.py

# Export session JSON for molab static previews (commit __marimo__/session/)
session:
    uv run marimo export session overview_notebook.py
    uv run marimo export session care_pack_notebook.py
