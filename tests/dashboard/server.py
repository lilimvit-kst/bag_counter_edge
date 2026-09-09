"""Test-only same-origin host for the real API and local dashboard assets."""
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from src.api.app import app

app.mount('/', StaticFiles(directory=Path(__file__).resolve().parents[2] / 'frontend', html=True))
