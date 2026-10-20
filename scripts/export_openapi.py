"""Экспорт OpenAPI-спецификации в docs/api/openapi.json (без запуска сервера).
Запуск из каталога backend:  python ../scripts/export_openapi.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import app  # noqa: E402

out = Path(__file__).resolve().parents[1] / "docs/api/openapi.json"
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", out)
