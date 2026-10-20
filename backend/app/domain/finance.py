"""Финансовые расчёты: аннуитет, сводка по оборотам, график платежей."""
from __future__ import annotations

import math
from datetime import date
from statistics import mean, pstdev


def annuity_payment(principal: float, annual_rate_pct: float, months: int) -> float:
    if months <= 0:
        raise ValueError("months must be positive")
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** -months)


def annuity_principal(payment: float, annual_rate_pct: float, months: int) -> float:
    """Обратная задача: какую сумму можно взять при заданном платеже."""
    if payment <= 0 or months <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return payment * months
    return payment * (1 - (1 + r) ** -months) / r


def overdraft_monthly_cost(limit: float, annual_rate_pct: float) -> float:
    """Нагрузка овердрафта: проценты при полном использовании лимита."""
    return limit * annual_rate_pct / 100 / 12


def round_down(value: float, step: int = 10_000) -> int:
    return int(math.floor(value / step) * step)


def summarize_turnovers(months: list[dict]) -> dict:
    """Сводка по помесячным оборотам: средний приход, оценка годовой выручки, стабильность."""
    rows = sorted(months, key=lambda m: m["month"])
    inflows = [float(m["inflow"]) for m in rows]
    if not inflows:
        return {"months_count": 0}
    avg = mean(inflows)
    cv = (pstdev(inflows) / avg) if avg > 0 and len(inflows) > 1 else None
    return {
        "months_count": len(rows),
        "period_from": rows[0]["month"],
        "period_to": rows[-1]["month"],
        "avg_monthly_inflow": round(avg, 2),
        "annual_revenue_estimate": round(avg * 12, 2),
        "stability_cv": round(cv, 3) if cv is not None else None,
    }


def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


def payment_schedule(principal: float, annual_rate_pct: float, months: int, start: date) -> list[dict]:
    payment = annuity_payment(principal, annual_rate_pct, months)
    r = annual_rate_pct / 100 / 12
    balance = principal
    rows = []
    for i in range(1, months + 1):
        interest = balance * r
        body = payment - interest
        if i == months:
            body = balance
            payment_i = body + interest
        else:
            payment_i = payment
        balance = max(balance - body, 0.0)
        rows.append(
            {
                "n": i,
                "date": add_months(start, i).isoformat(),
                "payment": round(payment_i, 2),
                "principal": round(body, 2),
                "interest": round(interest, 2),
                "balance": round(balance, 2),
            }
        )
    return rows
