"""Vercel Python 函数入口：所有 /api/* 请求都会被改写到这里。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
