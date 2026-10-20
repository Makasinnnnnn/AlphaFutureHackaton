"""Симулятор внешних источников данных (смоделированные интеграции).

Заменяет в проверяемой версии реальные сервисы, к которым у команды нет доступа:
- ЕГРЮЛ/ЕГРИП            GET /egrul/{inn}
- ФНС «Прозрачный бизнес» GET /fns/transparent-business/{inn}
- Бюро кредитных историй GET /bki/report/{inn}

Контракты упрощены, но сохраняют смысл: по ИНН — статус и реквизиты, налоговые признаки,
кредитные обязательства и платёжная дисциплина. Данные — синтетические
(data/synthetic/companies.json).

Имитация сбоев для проверки отказоустойчивости конвейера:
- MOCK_FAILURE_RATE (0..1) — доля случайных ответов 503 для всех источников;
- MOCK_LATENCY_MS — искусственная задержка ответа;
- у персоны с bki.simulate = "UNAVAILABLE" БКИ всегда отвечает 503.
"""
import asyncio
import json
import os
import random
from pathlib import Path

from fastapi import FastAPI, HTTPException

DATA_PATH = Path(os.getenv("SYNTHETIC_DATA", Path(__file__).resolve().parent.parent / "data/synthetic/companies.json"))
FAILURE_RATE = float(os.getenv("MOCK_FAILURE_RATE", "0"))
LATENCY_MS = int(os.getenv("MOCK_LATENCY_MS", "150"))

_companies = {c["egrul"]["inn"]: c for c in json.loads(DATA_PATH.read_text(encoding="utf-8"))["companies"]}

app = FastAPI(title="External sources simulator (ЕГРЮЛ / ФНС / БКИ)", version="1.0.0")


async def _io(source: str) -> None:
    if LATENCY_MS:
        await asyncio.sleep(LATENCY_MS / 1000 * random.uniform(0.5, 1.5))
    if FAILURE_RATE and random.random() < FAILURE_RATE:
        raise HTTPException(503, f"{source}: temporarily unavailable (simulated)")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "companies": len(_companies), "failure_rate": FAILURE_RATE}


@app.get("/egrul/{inn}", summary="Сведения из ЕГРЮЛ/ЕГРИП")
async def egrul(inn: str) -> dict:
    await _io("EGRUL")
    c = _companies.get(inn)
    if not c:
        raise HTTPException(404, "Субъект не найден")
    return {**c["egrul"], "source": "EGRUL_MOCK"}


@app.get("/fns/transparent-business/{inn}", summary="Сведения сервиса «Прозрачный бизнес»")
async def fns(inn: str) -> dict:
    await _io("FNS")
    c = _companies.get(inn)
    if not c:
        raise HTTPException(404, "Субъект не найден")
    return {"inn": inn, **c["fns"], "source": "FNS_MOCK"}


@app.get("/bki/report/{inn}", summary="Кредитный отчёт БКИ")
async def bki(inn: str) -> dict:
    await _io("BKI")
    c = _companies.get(inn)
    if c and c["bki"].get("simulate") == "UNAVAILABLE":
        raise HTTPException(503, "BKI: service unavailable (simulated)")
    if not c:  # субъект без кредитной истории
        return {"inn": inn, "has_history": False, "current_overdue_days": 0, "max_overdue_days_12m": 0,
                "obligations": [], "total_monthly_payments": 0, "inquiries_30d": 0, "source": "BKI_MOCK"}
    return {"inn": inn, **c["bki"], "source": "BKI_MOCK"}
