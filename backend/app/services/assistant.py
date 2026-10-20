"""Подбор продукта по описанию задачи.

Основной движок — правила по ключевым словам (работает всегда, без внешних зависимостей).
Опционально (LLM_ENABLED=true) задача классифицируется локальной open-weights моделью
через Ollama. При любой ошибке модели — прозрачный откат на правила.
"""
from __future__ import annotations

import json
import logging

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.decision import GRADE_PREMIUM
from app.domain.purposes import PURPOSES, match_purpose_rules
from app.schemas import Recommendation, RecommendOut
from app.services.products import list_products, to_out

log = logging.getLogger("assistant")

LLM_PROMPT = """Ты помогаешь предпринимателю выбрать кредит. Определи цель финансирования по описанию.
Возможные цели (код: описание):
{options}
Ответь строго JSON вида {{"purpose": "<код>"}} без пояснений. Если ни одна цель не подходит — {{"purpose": null}}.
Описание: {text}"""


def classify_llm(text: str) -> str | None:
    s = get_settings()
    options = "\n".join(f"{k}: {v['title']} — {v['hint']}" for k, v in PURPOSES.items())
    r = httpx.post(
        f"{s.ollama_url}/api/generate",
        json={"model": s.ollama_model, "prompt": LLM_PROMPT.format(options=options, text=text),
              "format": "json", "stream": False, "options": {"temperature": 0}},
        timeout=s.llm_timeout_sec,
    )
    r.raise_for_status()
    purpose = json.loads(r.json()["response"]).get("purpose")
    return purpose if purpose in PURPOSES else None


def recommend(db: Session, text: str | None, purpose: str | None) -> RecommendOut:
    engine = "rules"
    note = None
    if not purpose and text:
        if get_settings().llm_enabled:
            try:
                purpose = classify_llm(text)
                engine = "llm"
            except Exception as e:  # noqa: BLE001 — модель опциональна, падение не должно ломать сценарий
                log.warning("llm unavailable, fallback to rules", extra={"ctx": {"error": str(e)}})
        if not purpose:
            engine = "rules"
            hits = match_purpose_rules(text)
            purpose = hits[0][0] if hits else None
        if not purpose:
            note = "Не удалось однозначно определить задачу — показываем все продукты. Выберите цель из списка, чтобы получить подсказку точнее."

    products = {p.code: p for p in list_products(db)}
    recs: list[Recommendation] = []
    if purpose and purpose in PURPOSES:
        p = PURPOSES[purpose]
        for i, code in enumerate(p["products"]):
            if code in products:
                prod = products[code]
                recs.append(Recommendation(product=to_out(prod), why=p["why"][code], rank=i + 1,
                                           estimated_rate_from=float(prod.base_rate) + GRADE_PREMIUM["A"]))
    else:
        for i, prod in enumerate(products.values()):
            recs.append(Recommendation(product=to_out(prod), why=prod.short_description, rank=i + 1,
                                       estimated_rate_from=float(prod.base_rate)))
    return RecommendOut(
        purpose=purpose,
        purpose_title=PURPOSES[purpose]["title"] if purpose in PURPOSES else None,
        engine=engine,
        recommendations=recs,
        note=note,
    )
