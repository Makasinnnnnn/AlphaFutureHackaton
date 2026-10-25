"""Юнит-тесты доменной логики: скоринг, кредитное решение, state machine, распознавание выписки."""
import pytest
from datetime import date

from app.domain.decision import DecisionInput, ProductTerms, decide
from app.domain.finance import annuity_payment, annuity_principal, payment_schedule, summarize_turnovers
from app.domain.scoring import ScoringInput, grade_for, okved_risk, score
from app.domain.statement_parser import StatementParseError, parse_statement
from app.domain.statuses import Actor, Status, TransitionError, assert_transition, can_transition
from app.domain.validation import missing_items

WC = ProductTerms("WORKING_CAPITAL", "Оборотный", 100_000, 5_000_000, 3, 24, 19.0,
                  {"auto_approve_score": 60, "review_score": 45, "min_business_age_months": 6,
                   "max_revenue_share": 0.4, "max_dti": 0.5})
EQ = ProductTerms("EQUIPMENT", "Оборудование", 300_000, 30_000_000, 12, 60, 17.0,
                  {"auto_approve_score": 60, "review_score": 40, "min_business_age_months": 12,
                   "max_revenue_share": 0.8, "max_dti": 0.6, "max_ltv": 0.9})
OD = ProductTerms("OVERDRAFT", "Овердрафт", 50_000, 10_000_000, 12, 12, 21.0,
                  {"auto_approve_score": 70, "review_score": 55, "min_business_age_months": 6,
                   "max_turnover_share": 0.3, "max_dti": 0.5, "is_overdraft": True}, is_overdraft=True)


def good_profile(**kw) -> ScoringInput:
    base = dict(business_age_months=80, registry_status="ACTIVE", okved="56.10", bki_has_history=True,
                bki_current_overdue_days=0, bki_max_overdue_days_12m=0, bki_monthly_payments=40_000,
                fns_mass_address=False, fns_tax_arrears=0, fns_disqualified_director=False,
                avg_monthly_inflow=2_000_000, stability_cv=0.05, is_bank_client=True, bank_history_months=12)
    base.update(kw)
    return ScoringInput(**base)


# ---------- Скоринг ----------
def test_good_profile_scores_high():
    r = score(good_profile())
    assert r.score == 90 and r.grade == "A" and not r.stop_factors


def test_score_is_explainable_sum_of_factors():
    r = score(good_profile(okved="41.20", bki_max_overdue_days_12m=10))
    assert r.score == 50 + sum(f.points for f in r.factors)
    assert all(f.client_text for f in r.factors)


@pytest.mark.parametrize("kw,code", [
    ({"registry_status": "LIQUIDATED"}, "REGISTRY_STATUS"),
    ({"bki_current_overdue_days": 47}, "CURRENT_OVERDUE"),
    ({"fns_disqualified_director": True}, "DISQUALIFIED_DIRECTOR"),
])
def test_stop_factors(kw, code):
    r = score(good_profile(**kw))
    assert code in {s.code for s in r.stop_factors}


def test_score_clamped():
    r = score(good_profile(business_age_months=2, bki_current_overdue_days=10, stability_cv=0.9,
                           okved="41.20", fns_mass_address=True, fns_tax_arrears=1, is_bank_client=False,
                           bki_monthly_payments=5_000_000))
    assert 0 <= r.score <= 100


def test_okved_and_grade():
    assert okved_risk("62.01") == "low" and okved_risk("41.20") == "high" and okved_risk("47.71") == "medium"
    assert [grade_for(x) for x in (80, 65, 50, 10)] == ["A", "B", "C", "D"]


# ---------- Кредитное решение ----------
def inp(**kw) -> DecisionInput:
    base = dict(amount=2_000_000, term_months=12, avg_monthly_inflow=2_000_000,
                existing_monthly_payments=40_000, business_age_months=80)
    base.update(kw)
    return DecisionInput(**base)


def test_approved_within_limits():
    d = decide(WC, score(good_profile()), inp())
    assert d.outcome == "APPROVED" and d.offer.amount == 2_000_000 and d.offer.rate == 19.0


def test_stop_factor_rejects():
    d = decide(WC, score(good_profile(bki_current_overdue_days=60)), inp())
    assert d.outcome == "REJECTED" and any("просрочка" in r["text"] for r in d.reasons)


def test_counter_offer_when_amount_exceeds_revenue_limit():
    prof = good_profile(avg_monthly_inflow=650_000, bki_monthly_payments=0)
    d = decide(WC, score(prof), inp(amount=5_000_000, term_months=24, avg_monthly_inflow=650_000,
                                    existing_monthly_payments=0))
    assert d.outcome == "COUNTER_OFFER"
    assert d.offer.amount == 3_120_000  # 0.4 × 650 000 × 12, округление вниз до 10 000
    assert any("выручки" in r["text"] for r in d.reasons)


def test_counter_offer_prefers_longer_term_for_same_amount():
    # платёж не проходит по DTI на 6 мес, но проходит на более длинный срок
    prof = good_profile(avg_monthly_inflow=600_000, bki_monthly_payments=100_000)
    d = decide(WC, score(prof), inp(amount=1_500_000, term_months=6, avg_monthly_inflow=600_000,
                                    existing_monthly_payments=100_000))
    assert d.outcome == "COUNTER_OFFER"
    assert d.offer.amount == 1_500_000 and d.offer.term_months > 6


def test_gray_zone_goes_to_manual_review():
    prof = good_profile(business_age_months=50, bki_max_overdue_days_12m=12, okved="41.20",
                        bki_monthly_payments=240_000, avg_monthly_inflow=1_200_000, stability_cv=0.2)
    s = score(prof)
    assert 45 <= s.score < 60
    d = decide(WC, s, inp(amount=1_500_000, avg_monthly_inflow=1_200_000, existing_monthly_payments=240_000,
                          business_age_months=50))
    assert d.outcome == "MANUAL_REVIEW" and d.recommendation


def test_same_score_different_products_give_different_decisions():
    prof = good_profile(business_age_months=50, bki_max_overdue_days_12m=12, okved="41.20",
                        bki_monthly_payments=240_000, avg_monthly_inflow=1_200_000, stability_cv=0.2)
    s = score(prof)
    common = dict(avg_monthly_inflow=1_200_000, existing_monthly_payments=240_000, business_age_months=50)
    wc = decide(WC, s, inp(amount=1_000_000, **common))
    od = decide(OD, s, inp(amount=300_000, **common))
    assert wc.outcome == "MANUAL_REVIEW" and od.outcome == "REJECTED"


def test_young_business_equipment_gets_alternative_product():
    prof = good_profile(business_age_months=10, bki_has_history=False, okved="62.01",
                        avg_monthly_inflow=650_000, bki_monthly_payments=0)
    d = decide(EQ, score(prof), inp(amount=1_000_000, term_months=24, avg_monthly_inflow=650_000,
                                    existing_monthly_payments=0, business_age_months=10, equipment_cost=1_200_000),
               alternatives=[WC, EQ, OD])
    assert d.outcome == "COUNTER_OFFER" and d.offer.product_code == "WORKING_CAPITAL"


def test_equipment_ltv_limit():
    d = decide(EQ, score(good_profile()), inp(amount=2_000_000, term_months=36, equipment_cost=2_000_000))
    assert d.outcome == "COUNTER_OFFER" and d.offer.amount == 1_800_000


def test_overdraft_limit_from_turnover():
    d = decide(OD, score(good_profile()), inp(amount=1_000_000))
    assert d.outcome == "COUNTER_OFFER" and d.offer.amount == 600_000  # 30% от 2 млн


# ---------- Финансы ----------
def test_annuity_roundtrip():
    p = annuity_payment(1_000_000, 19, 12)
    assert abs(annuity_principal(p, 19, 12) - 1_000_000) < 0.01


def test_schedule_repays_principal():
    from datetime import date
    rows = payment_schedule(1_000_000, 19, 12, date(2026, 10, 20))
    assert len(rows) == 12 and rows[-1]["balance"] == 0
    assert abs(sum(r["principal"] for r in rows) - 1_000_000) < 1


def test_summarize_turnovers():
    s = summarize_turnovers([{"month": "2026-01", "inflow": 100}, {"month": "2026-02", "inflow": 100}])
    assert s["avg_monthly_inflow"] == 100 and s["annual_revenue_estimate"] == 1200 and s["stability_cv"] == 0


# ---------- State machine ----------
def test_valid_and_invalid_transitions():
    assert can_transition(Status.DRAFT, Status.SUBMITTED, Actor.CLIENT)
    assert not can_transition(Status.DRAFT, Status.APPROVED, Actor.CLIENT)
    assert not can_transition(Status.SCORING, Status.APPROVED, Actor.CLIENT)  # решение принимает только система
    assert not can_transition(Status.MANUAL_REVIEW, Status.APPROVED, Actor.CLIENT)
    assert can_transition(Status.MANUAL_REVIEW, Status.APPROVED, Actor.ANALYST)
    with pytest.raises(TransitionError):
        assert_transition(Status.ISSUED, Status.CANCELLED, Actor.CLIENT)


def test_terminal_statuses_have_no_exits():
    from app.domain.statuses import TERMINAL, TRANSITIONS
    assert not [k for k in TRANSITIONS if k[0] in TERMINAL]


# ---------- Полнота заявки ----------
def test_missing_items_for_equipment_without_docs():
    items = missing_items(product_code="EQUIPMENT", requires_collateral=True, financials=None,
                          collateral=None, document_kinds=set())
    assert {i["code"] for i in items} == {"STATEMENT", "EQUIPMENT_INFO", "EQUIPMENT_INVOICE"}


def test_complete_application_has_no_missing_items():
    fin = {"months": [{"month": f"2026-0{i}", "inflow": 1} for i in range(1, 7)]}
    assert missing_items(product_code="WORKING_CAPITAL", requires_collateral=False, financials=fin,
                         collateral=None, document_kinds=set(), as_of=date(2026, 7, 1)) == []


# ---------- Распознавание выписки ----------
def test_parse_statement_in_out_columns():
    raw = "Дата;Приход;Расход;Назначение\n01.04.2026;100 000,50;;Оплата\n15.04.2026;;30000;Аренда\n02.05.2026;50000;;Оплата\n".encode()
    r = parse_statement(raw)
    assert r["months"][0] == {"month": "2026-04", "inflow": 100000.5, "outflow": 30000.0, "operations": 2}
    assert len(r["months"]) == 2 and r["warnings"]


def test_parse_statement_signed_amount_cp1251():
    raw = "date,amount,purpose\n2026-01-10,1000,a\n2026-01-11,-400,b\n2026-02-01,500,c\n2026-03-01,700,d\n".encode("cp1251")
    r = parse_statement(raw, as_of=date(2026, 4, 1))
    assert [m["inflow"] for m in r["months"]] == [1000, 500, 700] and r["months"][0]["outflow"] == 400
    assert not r["warnings"]


def test_parse_statement_errors():
    with pytest.raises(StatementParseError):
        parse_statement(b"foo;bar\n1;2\n")
    with pytest.raises(StatementParseError):
        parse_statement(b"")
