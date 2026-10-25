"""Распознавание банковской выписки (CSV) → помесячные обороты.

Клиенты без доступной истории оборотов загружают выписку из другого банка. Вместо
ручного ввода выручки система сама считает поступления и списания по месяцам.
Поддерживаются популярные варианты выгрузок:
- колонки «Дата; Сумма» (знак суммы = направление);
- колонки «Дата; Приход/Поступление/Кредит; Расход/Списание/Дебет».
Разделитель «;», «,» или табуляция. Даты ДД.ММ.ГГГГ или ГГГГ-ММ-ДД.
"""
from __future__ import annotations

import csv
import io
import math
import re
from app.domain.statement_history import contiguous_tail, history_problem
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
    s = re.sub(r"\s|₽|руб\.?", "", str(value), flags=re.IGNORECASE).replace(",", ".")
    if s in ("", "-"):
        return 0.0
    try:
        number = float(s)
        if not math.isfinite(number) or abs(number) > 1e15:
            raise ValueError("non-finite or out-of-range amount")
        return number
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


def parse_statement(raw: bytes, *, as_of: date | None = None) -> dict:
    text = _decode(raw).strip()
    if not text:
        raise StatementParseError("Файл пустой.")
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=";,\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";"
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    except csv.Error as exc:
        raise StatementParseError('Не удалось прочитать CSV: проверьте разделители и длину полей.') from exc
    header, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
    if not body:
        raise StatementParseError("В файле нет операций.")

    i_date = _find(header, DATE_KEYS)
    i_amt = _find(header, AMOUNT_KEYS)
    i_in, i_out = _find(header, IN_KEYS), _find(header, OUT_KEYS)
    if i_date is None or (i_amt is None and i_in is None):
        raise StatementParseError(
            "Не найдены колонки с датой и суммой. Ожидаются «Дата» и «Сумма» или «Приход»/«Расход»."
        )

    agg: dict[str, dict[str, float]] = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0, "ops": 0})
    required = [i for i in (i_date, i_amt if i_in is None else i_in, i_out) if i is not None]
    for row_number, r in enumerate(body, start=2):
        if len(r) <= max(required):
            raise StatementParseError(f"В строке {row_number} не хватает колонок.")
        d = _date(r[i_date])
        if d > (as_of or date.today()):
            raise StatementParseError(f"В строке {row_number} дата операции находится в будущем.")
        key = f"{d.year:04d}-{d.month:02d}"
        if i_in is not None:
            inflow = _num(r[i_in]) if i_in < len(r) else 0.0
            outflow = abs(_num(r[i_out])) if i_out is not None and i_out < len(r) else 0.0
            if inflow < 0:
                raise StatementParseError(f"В строке {row_number} поступление не может быть отрицательным.")
        else:
            amt = _num(r[i_amt])
            inflow, outflow = (amt, 0.0) if amt >= 0 else (0.0, -amt)
        agg[key]["inflow"] += inflow
        agg[key]["outflow"] += outflow
        agg[key]["ops"] += 1
        if max(agg[key]["inflow"], agg[key]["outflow"]) > 1e15:
            raise StatementParseError("Суммарный оборот за месяц превышает допустимый диапазон.")

    months = [
        {"month": m, "inflow": round(v["inflow"], 2), "outflow": round(v["outflow"], 2), "operations": v["ops"]}
        for m, v in sorted(agg.items())
    ]
    warnings = []
    problem = history_problem(months, as_of)
    if problem:
        warnings.append(problem)
    tail = contiguous_tail(months)
    if len(tail) < len(months):
        warnings.append(f"В истории есть пропуски. Для оценки учтён последний непрерывный период: {len(tail)} мес.")
    return {"rows": len(body), "months": months, "warnings": warnings}
