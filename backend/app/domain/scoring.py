"""Скоринг: прозрачная балльная модель оценки риска заёмщика.

Скоринг описывает ПРОФИЛЬ заёмщика (бизнес, кредитная история, обороты) и не зависит
от параметров конкретной заявки. Сумма, срок и продукт учитываются отдельно — в слое
кредитного решения (decision.py). Поэтому одинаковый скоринг может давать разные
решения для разных продуктов, как и требует кейс.

Шкала: 0..100, выше — ниже риск. Базовое значение 50, каждый фактор даёт ± баллы.
Стоп-факторы делают решение отрицательным независимо от балла.
Все функции чистые — легко тестируются и объясняются.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

BASE_SCORE = 50

# Риск отрасли по ОКВЭД (упрощённо, по префиксу кода)
OKVED_RISK = {
    "low": ["62", "63", "85", "86", "69", "70.22", "71", "72"],
    "high": ["41", "42", "43", "68", "92", "01", "55"],
}

STOP_REGISTRY_STATUSES = {"LIQUIDATED", "LIQUIDATING", "BANKRUPT"}


@dataclass
class ScoringInput:
    business_age_months: int
    registry_status: str  # ACTIVE | LIQUIDATED | ...
    okved: str | None
    bki_has_history: bool
    bki_current_overdue_days: int
    bki_max_overdue_days_12m: int
    bki_monthly_payments: float
    fns_mass_address: bool
    fns_tax_arrears: float
    fns_disqualified_director: bool
    avg_monthly_inflow: float
    stability_cv: float | None
    is_bank_client: bool
    bank_history_months: int


@dataclass
class Factor:
    code: str
    name: str
    value: str
    points: int
    client_text: str

    @property
    def impact(self) -> str:
        return "positive" if self.points > 0 else "negative" if self.points < 0 else "neutral"


@dataclass
class StopFactor:
    code: str
    client_text: str


@dataclass
class ScoreResult:
    score: int
    grade: str
    factors: list[Factor] = field(default_factory=list)
    stop_factors: list[StopFactor] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model": "points-v1",
            "base": BASE_SCORE,
            "score": self.score,
            "grade": self.grade,
            "factors": [asdict(f) | {"impact": f.impact} for f in self.factors],
            "stop_factors": [asdict(s) for s in self.stop_factors],
        }


def okved_risk(okved: str | None) -> str:
    if not okved:
        return "medium"
    for level in ("low", "high"):
        if any(okved.startswith(p) for p in OKVED_RISK[level]):
            return level
    return "medium"


def grade_for(score: int) -> str:
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def score(inp: ScoringInput) -> ScoreResult:
    factors: list[Factor] = []
    stops: list[StopFactor] = []

    # --- Стоп-факторы ---
    if inp.registry_status in STOP_REGISTRY_STATUSES:
        stops.append(StopFactor("REGISTRY_STATUS", "По данным реестра компания ликвидирована или находится в процессе ликвидации."))
    if inp.fns_disqualified_director:
        stops.append(StopFactor("DISQUALIFIED_DIRECTOR", "Руководитель компании числится в реестре дисквалифицированных лиц."))
    if inp.bki_current_overdue_days > 30:
        stops.append(StopFactor("CURRENT_OVERDUE", "Есть текущая просрочка по действующим кредитам более 30 дней."))

    # --- Возраст бизнеса ---
    age = inp.business_age_months
    if age < 6:
        pts, txt = -20, "Бизнес работает меньше полугода — у банка мало истории для оценки."
    elif age < 12:
        pts, txt = -10, "Бизнесу меньше года — это повышает риск в оценке банка."
    elif age < 36:
        pts, txt = 0, "Бизнес работает 1–3 года."
    elif age < 60:
        pts, txt = 5, "Бизнес работает больше трёх лет."
    else:
        pts, txt = 10, "Бизнес работает больше пяти лет — это положительный фактор."
    factors.append(Factor("BUSINESS_AGE", "Возраст бизнеса", f"{age} мес.", pts, txt))

    # --- Кредитная история ---
    if inp.bki_current_overdue_days > 30:
        pts, txt = -30, "Есть текущая просрочка более 30 дней."
    elif inp.bki_current_overdue_days > 0:
        pts, txt = -20, "Есть текущая просрочка по кредитам."
    elif inp.bki_max_overdue_days_12m > 30:
        pts, txt = -10, "За последний год были просрочки более 30 дней."
    elif inp.bki_max_overdue_days_12m > 0:
        pts, txt = -5, "За последний год были небольшие просрочки."
    elif inp.bki_has_history:
        pts, txt = 10, "Хорошая кредитная история без просрочек."
    else:
        pts, txt = 0, "Кредитной истории пока нет — это нейтральный фактор."
    value = (
        f"текущая просрочка {inp.bki_current_overdue_days} дн., макс. за 12 мес. {inp.bki_max_overdue_days_12m} дн."
        if inp.bki_has_history
        else "нет истории"
    )
    factors.append(Factor("CREDIT_HISTORY", "Кредитная история (БКИ)", value, pts, txt))

    # --- Текущая долговая нагрузка ---
    if inp.avg_monthly_inflow > 0:
        load = inp.bki_monthly_payments / inp.avg_monthly_inflow
        if load < 0.1:
            pts, txt = 5, "Текущие платежи по кредитам небольшие относительно оборотов."
        elif load < 0.3:
            pts, txt = 0, "Умеренная текущая долговая нагрузка."
        elif load < 0.5:
            pts, txt = -10, "Заметная текущая долговая нагрузка."
        else:
            pts, txt = -20, "Высокая текущая долговая нагрузка относительно оборотов."
        factors.append(Factor("DEBT_LOAD", "Текущая долговая нагрузка", f"{load:.0%} от среднемесячных поступлений", pts, txt))

    # --- Стабильность оборотов ---
    if inp.stability_cv is not None:
        cv = inp.stability_cv
        if cv < 0.15:
            pts, txt = 10, "Обороты стабильные."
        elif cv < 0.3:
            pts, txt = 0, "Обороты умеренно колеблются."
        else:
            pts, txt = -10, "Обороты сильно колеблются от месяца к месяцу."
        factors.append(Factor("TURNOVER_STABILITY", "Стабильность оборотов", f"коэф. вариации {cv:.2f}", pts, txt))

    # --- Отрасль ---
    risk = okved_risk(inp.okved)
    pts = {"low": 5, "medium": 0, "high": -5}[risk]
    txt = {
        "low": "Отрасль с низким кредитным риском.",
        "medium": "Отрасль со средним кредитным риском.",
        "high": "Отрасль с повышенным кредитным риском.",
    }[risk]
    factors.append(Factor("INDUSTRY", "Отраслевой риск (ОКВЭД)", f"{inp.okved or '—'} ({risk})", pts, txt))

    # --- Сведения ФНС ---
    if inp.fns_mass_address:
        factors.append(Factor("MASS_ADDRESS", "Адрес массовой регистрации", "да", -10, "Компания зарегистрирована по адресу массовой регистрации."))
    if inp.fns_tax_arrears > 0:
        factors.append(Factor("TAX_ARREARS", "Задолженность по налогам", f"{inp.fns_tax_arrears:,.0f} ₽".replace(",", " "), -15, "Есть задолженность по налогам."))

    # --- Клиент банка ---
    if inp.is_bank_client and inp.bank_history_months >= 6:
        factors.append(Factor("BANK_CLIENT", "Клиент банка", f"{inp.bank_history_months} мес. оборотов по счёту", 5, "Банк видит обороты по вашему счёту — это повышает точность оценки."))

    total = BASE_SCORE + sum(f.points for f in factors)
    total = max(0, min(100, total))
    return ScoreResult(score=total, grade=grade_for(total), factors=factors, stop_factors=stops)
