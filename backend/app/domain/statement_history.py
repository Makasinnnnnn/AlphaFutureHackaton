"""Explicit demo policy, not a bank regulation: 3 consecutive months, latest within 2 months."""
from datetime import date
import re

MIN_MONTHS = 3
MAX_AGE_MONTHS = 2


def month_index(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value):
        raise ValueError('Некорректный месяц истории оборотов')
    year, month = map(int, value.split('-'))
    return year * 12 + month - 1


def contiguous_tail(months: list[dict]) -> list[dict]:
    rows = sorted(months, key=lambda row: month_index(row.get('month')))
    if not rows:
        return []
    tail = [rows[-1]]
    for row in reversed(rows[:-1]):
        if month_index(tail[0]['month']) - month_index(row['month']) != 1:
            break
        tail.insert(0, row)
    return tail


def history_problem(months: list[dict], as_of: date | None = None) -> str | None:
    try:
        tail = contiguous_tail(months)
        if len(tail) < MIN_MONTHS:
            return 'Нужны минимум 3 последовательных месяца оборотов без пропусков; лучше приложить 6 месяцев.'
        current = as_of or date.today()
        lag = current.year * 12 + current.month - 1 - month_index(tail[-1]['month'])
        if lag < 0:
            return 'В истории есть будущие месяцы. Проверьте даты выписки.'
        if lag > MAX_AGE_MONTHS:
            return 'История устарела: последний месяц должен быть не старше 2 месяцев. Загрузите свежую выписку.'
    except (ValueError, TypeError, KeyError):
        return 'Не удалось определить период оборотов. Загрузите выписку с корректными датами.'
    return None
