"""Regressions found while reviewing the submitted prototype."""
from datetime import date, timedelta

import pytest

from app.domain.finance import summarize_turnovers
from app.domain.statement_parser import StatementParseError, parse_statement
from tests.test_domain import WC, good_profile, inp
from app.domain.decision import decide
from app.domain.scoring import score


@pytest.mark.parametrize("value", ["NaN", "nan", "inf", "-inf", "Infinity", "1e309", "1e16"])
def test_statement_rejects_non_finite_and_out_of_range(value):
    with pytest.raises(StatementParseError):
        parse_statement(f"Дата;Сумма\n2026-01-15;{value}".encode())


@pytest.mark.parametrize("value", ["123.45", "123,45", "123,45 руб.", "123.45 ₽"])
def test_statement_preserves_decimal_separator(value):
    parsed = parse_statement(f"Дата;Сумма\n2026-01-15;{value}".encode())
    assert parsed["months"][0]["inflow"] == 123.45


@pytest.mark.parametrize("body", ["Дата;Сумма", "Дата;Сумма\n2026-01-15", "Дата;Приход;Расход\n2026-01-15;-20;0"])
def test_statement_rejects_missing_operations_columns_or_negative_inflow(body):
    with pytest.raises(StatementParseError):
        parse_statement(body.encode())


def test_statement_rejects_future_operations():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(StatementParseError, match="будущем"):
        parse_statement(f"Дата;Сумма\n{tomorrow};100".encode())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 1e16])
def test_turnover_summary_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        summarize_turnovers([{"month": "2026-01", "inflow": value, "outflow": 0}])


def test_counteroffer_keeps_request_limits_and_separate_feasible_offer_limits():
    d = decide(WC, score(good_profile(avg_monthly_inflow=600_000, bki_monthly_payments=100_000)),
               inp(amount=1_500_000, term_months=6, avg_monthly_inflow=600_000, existing_monthly_payments=100_000))
    assert d.offer.term_months == 9
    assert d.limits["dti"] < 1_500_000
    assert min(d.offer_limits.values()) >= 1_500_000
    assert d.to_dict()["offer_limits"] == d.offer_limits
    assert d.requested_terms["monthly_payment"] > d.offer.monthly_payment
    assert d.requested_terms["monthly_payment"] * 6 < d.offer.monthly_payment * 9
