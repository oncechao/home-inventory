import importlib.util
import json
from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]


def test_vercel_entry_exposes_fastapi_app():
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.app, FastAPI)


def test_vercel_config_routes_api_and_spa():
    config = json.loads((ROOT / "vercel.json").read_text())
    rewrites = config["rewrites"]
    assert rewrites[0] == {"source": "/api/(.*)", "destination": "/api/index"}
    assert rewrites[-1] == {"source": "/(.*)", "destination": "/index.html"}
    assert config["outputDirectory"] == "frontend/dist"
