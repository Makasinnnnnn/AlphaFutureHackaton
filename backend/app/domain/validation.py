"""Проверка полноты заявки (этап VALIDATION).

Возвращает список того, чего не хватает для решения. Пустой список — можно идти дальше.
Формат элементов: {"code": ..., "text": ...} — текст показывается клиенту как есть.
"""
from __future__ import annotations

from datetime import date
from app.domain.statement_history import history_problem


def missing_items(
    *,
    product_code: str,
    requires_collateral: bool,
    financials: dict | None,
    collateral: dict | None,
    document_kinds: set[str],
    as_of: date | None = None,
) -> list[dict]:
    items: list[dict] = []

    months = (financials or {}).get("months") or []
    problem = history_problem(months, as_of)
    if problem:
        items.append(
            {
                "code": "STATEMENT",
                "text": problem + " Поддерживается CSV из интернет-банка.",
            }
        )

    if requires_collateral:
        c = collateral or {}
        if not c.get("equipment_name") or not c.get("equipment_cost"):
            items.append({"code": "EQUIPMENT_INFO", "text": "Укажите, какое оборудование покупаете, и его стоимость."})
        if "EQUIPMENT_INVOICE" not in document_kinds:
            items.append(
                {"code": "EQUIPMENT_INVOICE", "text": "Приложите счёт или спецификацию от поставщика оборудования."}
            )
    return items
