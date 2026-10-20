"""Распознавание банковской выписки (CSV) → помесячные обороты.

Клиенты, у которых нет счёта в банке, загружают выписку из другого банка. Вместо
ручного ввода выручки система сама считает поступления и списания по месяцам.
Поддерживаются популярные варианты выгрузок:
- колонки «Дата; Сумма» (знак суммы = направление);
- колонки «Дата; Приход/Поступление/Кредит; Расход/Списание/Дебет».
Разделитель «;», «,» или табуляция. Даты ДД.ММ.ГГГГ или ГГГГ-ММ-ДД.
"""
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import date, datetime

DATE_KEYS = ("дата", "date", "дата операции")
AMOUNT_KEYS = ("сумма", "amount", "сумма операции")
IN_KEYS = ("приход", "поступление", "кредит", "credit", "inflow", "зачисление")
OUT_KEYS = ("расход", "списание", "дебет", "debit", "outflow")


class StatementParseError(ValueError):
    pass


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise StatementParseError("Не удалось определить кодировку файла (ожидается UTF-8 или Windows-1251).")


def _num(value: str | None) -> float:
    if value is None:
        return 0.0
    s = re.sub(r"[\s ₽руб.]", "", str(value)).replace(",", ".")
    if s in ("", "-"):
        return 0.0
    try:
        return float(s)
    except ValueError as e:
        raise StatementParseError(f"Не удалось распознать сумму «{value}».") from e


def _date(value: str) -> date:
    v = value.strip()[:10]
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise StatementParseError(f"Не удалось распознать дату «{value}».")


def _find(header: list[str], keys: tuple[str, ...]) -> int | None:
    for i, h in enumerate(header):
        hn = h.strip().lower()
        if any(hn == k or hn.startswith(k) for k in keys):
            return i
    return None


def parse_statement(raw: bytes) -> dict:
    text = _decode(raw).strip()
    if not text:
        raise StatementParseError("Файл пустой.")
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=";,\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";"
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    header, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]

    i_date = _find(header, DATE_KEYS)
    i_amt = _find(header, AMOUNT_KEYS)
    i_in, i_out = _find(header, IN_KEYS), _find(header, OUT_KEYS)
    if i_date is None or (i_amt is None and i_in is None):
        raise StatementParseError(
            "Не найдены колонки с датой и суммой. Ожидаются «Дата» и «Сумма» или «Приход»/«Расход»."
        )

    agg: dict[str, dict[str, float]] = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0, "ops": 0})
    for r in body:
        d = _date(r[i_date])
        key = f"{d.year:04d}-{d.month:02d}"
        if i_in is not None:
            inflow = _num(r[i_in]) if i_in < len(r) else 0.0
            outflow = abs(_num(r[i_out])) if i_out is not None and i_out < len(r) else 0.0
        else:
            amt = _num(r[i_amt])
            inflow, outflow = (amt, 0.0) if amt >= 0 else (0.0, -amt)
        agg[key]["inflow"] += inflow
        agg[key]["outflow"] += outflow
        agg[key]["ops"] += 1

    months = [
        {"month": m, "inflow": round(v["inflow"], 2), "outflow": round(v["outflow"], 2), "operations": v["ops"]}
        for m, v in sorted(agg.items())
    ]
    warnings = []
    if len(months) < 3:
        warnings.append("В выписке меньше 3 месяцев — для оценки нужна выписка минимум за 3, лучше за 6 месяцев.")
    return {"rows": len(body), "months": months, "warnings": warnings}
