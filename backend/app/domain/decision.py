"""Кредитное решение — правила поверх скоринга.

Скоринг (scoring.py) говорит, насколько рискован заёмщик. Решение учитывает ещё и
продукт, запрошенную сумму и срок, обороты, залог и внутренние ограничения банка:

1. Стоп-факторы                          → REJECTED
2. Бизнес моложе минимума для продукта   → альтернативный продукт (COUNTER_OFFER) или REJECTED
3. Балл ниже порога рассмотрения продукта → REJECTED
4. Запрос укладывается в лимиты:
       балл ≥ порога авто-одобрения        → APPROVED
       иначе (серая зона)                  → MANUAL_REVIEW
5. Запрос не укладывается в лимиты:
       ищем ту же сумму на больший срок или максимально доступную сумму
       балл ≥ порога авто-одобрения        → COUNTER_OFFER
       иначе                               → MANUAL_REVIEW (с рекомендацией аналитику)
       доступная сумма < минимума продукта → REJECTED

Лимиты продукта:
- max_revenue_share — сумма не больше доли годовой выручки (для овердрафта — доли среднемесячного оборота);
- max_dti — все платежи по кредитам не больше доли среднемесячных поступлений;
- max_ltv — для кредита на оборудование сумма не больше доли стоимости оборудования.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.finance import (
    annuity_payment,
    annuity_principal,
    overdraft_monthly_cost,
    round_down,
)
from app.domain.scoring import ScoreResult

GRADE_PREMIUM = {"A": 0.0, "B": 1.5, "C": 3.5, "D": 6.0}


@dataclass
class ProductTerms:
    code: str
    name: str
    min_amount: float
    max_amount: float
    min_term: int
    max_term: int
    base_rate: float
    rules: dict
    is_overdraft: bool = False


@dataclass
class DecisionInput:
    amount: float
    term_months: int
    avg_monthly_inflow: float
    existing_monthly_payments: float
    business_age_months: int
    equipment_cost: float | None = None


@dataclass
class Offer:
    product_code: str
    product_name: str
    amount: float
    term_months: int
    rate: float
    monthly_payment: float

    def to_dict(self) -> dict:
        return {
            "product_code": self.product_code,
            "product_name": self.product_name,
            "amount": self.amount,
            "term_months": self.term_months,
            "rate": self.rate,
            "monthly_payment": round(self.monthly_payment, 2),
        }


@dataclass
class Decision:
    outcome: str  # APPROVED | COUNTER_OFFER | MANUAL_REVIEW | REJECTED
    offer: Offer | None = None
    recommendation: str | None = None  # для аналитика в MANUAL_REVIEW
    reasons: list[dict] = field(default_factory=list)  # объяснение клиенту
    limits: dict = field(default_factory=dict)
    offer_limits: dict = field(default_factory=dict)
    requested_terms: dict = field(default_factory=dict)
    rules_fired: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "offer": self.offer.to_dict() if self.offer else None,
            "recommendation": self.recommendation,
            "reasons": self.reasons,
            "limits": self.limits,
            "offer_limits": self.offer_limits,
            "requested_terms": self.requested_terms,
            "rules_fired": self.rules_fired,
        }


def rate_for(product: ProductTerms, grade: str) -> float:
    return round(product.base_rate + GRADE_PREMIUM.get(grade, 6.0), 2)


def monthly_load(product: ProductTerms, amount: float, rate: float, term: int) -> float:
    if product.is_overdraft:
        return overdraft_monthly_cost(amount, rate)
    return annuity_payment(amount, rate, term)


def max_amount_for_term(product: ProductTerms, inp: DecisionInput, rate: float, term: int) -> tuple[float, dict]:
    """Максимальная сумма, проходящая все лимиты продукта при заданном сроке."""
    rules = product.rules
    limits: dict[str, float] = {"product_max": product.max_amount}

    if product.is_overdraft:
        limits["turnover"] = inp.avg_monthly_inflow * rules.get("max_turnover_share", 0.3)
    else:
        limits["revenue"] = inp.avg_monthly_inflow * 12 * rules.get("max_revenue_share", 0.4)

    payment_cap = inp.avg_monthly_inflow * rules.get("max_dti", 0.5) - inp.existing_monthly_payments
    if product.is_overdraft:
        limits["dti"] = max(payment_cap, 0) / (rate / 100 / 12) if rate > 0 else product.max_amount
    else:
        limits["dti"] = annuity_principal(max(payment_cap, 0), rate, term)

    if rules.get("max_ltv") and inp.equipment_cost:
        limits["collateral"] = inp.equipment_cost * rules["max_ltv"]

    return min(limits.values()), {k: round(v, 2) for k, v in limits.items()}


LIMIT_TEXT = {
    "product_max": "Сумма превышает максимум для этого продукта.",
    "revenue": "Сумма великовата относительно выручки бизнеса.",
    "turnover": "Лимит овердрафта зависит от среднемесячных поступлений на счёт.",
    "dti": "Ежемесячный платёж был бы слишком большим относительно поступлений на счёт.",
    "collateral": "Кредит на оборудование выдаётся в пределах 90% его стоимости — остальное первоначальный взнос.",
}


def _client_reasons(score: ScoreResult, limit: str | None = None, extra: list[dict] | None = None) -> list[dict]:
    reasons: list[dict] = []
    for s in score.stop_factors:
        reasons.append({"impact": "negative", "text": s.client_text})
    for f in sorted(score.factors, key=lambda f: f.points):
        if f.points != 0:
            reasons.append({"impact": f.impact, "text": f.client_text})
    if limit:
        reasons.insert(0, {"impact": "negative", "text": LIMIT_TEXT[limit]})
    if extra:
        reasons = extra + reasons
    return reasons


def decide(
    product: ProductTerms,
    score: ScoreResult,
    inp: DecisionInput,
    alternatives: list[ProductTerms] | None = None,
) -> Decision:
    rules = product.rules
    rate = rate_for(product, score.grade)

    # 1. Стоп-факторы
    if score.stop_factors:
        return Decision(
            "REJECTED",
            reasons=_client_reasons(score),
            rules_fired=[f"STOP:{s.code}" for s in score.stop_factors],
        )

    # 2. Возраст бизнеса меньше минимума продукта → пробуем альтернативный продукт
    min_age = rules.get("min_business_age_months", 0)
    if inp.business_age_months < min_age:
        for alt in alternatives or []:
            if alt.code == product.code or inp.business_age_months < alt.rules.get("min_business_age_months", 0):
                continue
            alt_inp = DecisionInput(**{**inp.__dict__, "term_months": min(max(inp.term_months, alt.min_term), alt.max_term)})
            alt_decision = decide(alt, score, alt_inp, alternatives=None)
            if alt_decision.outcome in ("APPROVED", "COUNTER_OFFER"):
                alt_decision.outcome = "COUNTER_OFFER"
                alt_decision.rules_fired.insert(0, f"MIN_AGE:{product.code}->ALT:{alt.code}")
                alt_decision.reasons.insert(
                    0,
                    {
                        "impact": "negative",
                        "text": f"Продукт «{product.name}» доступен бизнесу старше {min_age} мес. "
                        f"Предлагаем «{alt.name}» — он подходит под вашу ситуацию.",
                    },
                )
                return alt_decision
        return Decision(
            "REJECTED",
            reasons=_client_reasons(
                score,
                extra=[{"impact": "negative", "text": f"Продукт доступен бизнесу старше {min_age} мес."}],
            ),
            rules_fired=[f"MIN_AGE:{product.code}"],
        )

    # 3. Балл ниже порога рассмотрения
    if score.score < rules["review_score"]:
        return Decision(
            "REJECTED",
            reasons=_client_reasons(score),
            rules_fired=[f"SCORE<{rules['review_score']}"],
        )

    auto = score.score >= rules["auto_approve_score"]
    max_amt, limits = max_amount_for_term(product, inp, rate, inp.term_months)
    binding = min(limits, key=limits.get)

    # 4. Запрос укладывается в лимиты
    if inp.amount <= max_amt:
        offer = Offer(product.code, product.name, round(inp.amount, 2), inp.term_months, rate,
                      monthly_load(product, inp.amount, rate, inp.term_months))
        if auto:
            return Decision("APPROVED", offer=offer, reasons=_client_reasons(score), limits=limits,
                            rules_fired=[f"SCORE>={rules['auto_approve_score']}", "WITHIN_LIMITS"])
        return Decision(
            "MANUAL_REVIEW",
            offer=offer,
            recommendation="Запрос в лимитах, балл в серой зоне — рекомендуется одобрить на запрошенных условиях после проверки.",
            reasons=_client_reasons(score),
            limits=limits,
            rules_fired=[f"{rules['review_score']}<=SCORE<{rules['auto_approve_score']}", "WITHIN_LIMITS"],
        )

    # 5. Запрос больше лимита → контрпредложение
    counter: Offer | None = None
    if not product.is_overdraft:
        for term in range(inp.term_months + 1, product.max_term + 1):
            m, _ = max_amount_for_term(product, inp, rate, term)
            if inp.amount <= m:
                counter = Offer(product.code, product.name, round(inp.amount, 2), term, rate,
                                annuity_payment(inp.amount, rate, term))
                break
    if counter is None:
        best_term = inp.term_months
        best_amt = round_down(max_amt)
        if not product.is_overdraft and best_amt < product.min_amount:
            m, _ = max_amount_for_term(product, inp, rate, product.max_term)
            best_term, best_amt = product.max_term, round_down(m)
        if best_amt >= product.min_amount:
            counter = Offer(product.code, product.name, best_amt, best_term, rate,
                            monthly_load(product, best_amt, rate, best_term))

    if counter is None:
        return Decision(
            "REJECTED",
            reasons=_client_reasons(score, limit=binding),
            limits=limits,
            rules_fired=[f"LIMIT:{binding}", "BELOW_PRODUCT_MIN"],
        )

    reasons = _client_reasons(score, limit=binding)
    _, offer_limits = max_amount_for_term(product, inp, rate, counter.term_months)
    requested_terms = {
        "rate": rate,
        "monthly_payment": round(monthly_load(product, inp.amount, rate, inp.term_months), 2),
        "is_overdraft": product.is_overdraft,
    }
    if auto:
        return Decision("COUNTER_OFFER", offer=counter, reasons=reasons, limits=limits, offer_limits=offer_limits,
                        requested_terms=requested_terms,
                        rules_fired=[f"LIMIT:{binding}", "COUNTER"])
    return Decision(
        "MANUAL_REVIEW",
        offer=counter,
        recommendation="Запрос выше лимита, балл в серой зоне — рекомендуется контрпредложение на указанных условиях.",
        reasons=reasons,
        limits=limits,
        offer_limits=offer_limits,
        requested_terms=requested_terms,
        rules_fired=[f"LIMIT:{binding}", "GRAY_ZONE"],
    )
