"""Автоматические этапы кредитного конвейера.

Каждый вызов `process_step` продвигает заявку ровно на один этап. Воркер (app/worker.py)
вызывает его для заявок в статусах SUBMITTED / VALIDATION / ENRICHMENT / SCORING,
у которых подошло время next_action_at. Между этапами — небольшая пауза, чтобы
клиент видел движение заявки в интерфейсе (в продакшене пауза = 0).
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.decision import DecisionInput, decide
from app.domain.scoring import STOP_REGISTRY_STATUSES, ScoringInput, score
from app.domain.statuses import Actor, Status
from app.domain.validation import missing_items
from app.integrations.client import CallResult, IntegrationClient
from app.models import Application, ExternalCheck, Product
from app.services.companies import apply_registry_data, bank_financials, bank_history_months, months_between
from app.services.products import to_terms
from app.services.workflow import add_event, now, transition

log = logging.getLogger("pipeline")


def process_step(db: Session, app: Application, client: IntegrationClient | None = None) -> None:
    status = Status(app.status)
    if status == Status.SUBMITTED:
        transition(db, app, Status.VALIDATION, Actor.SYSTEM, reason="Заявка принята в обработку")
    elif status == Status.VALIDATION:
        _validate(db, app)
    elif status == Status.ENRICHMENT:
        _enrich(db, app, client or IntegrationClient())
    elif status == Status.SCORING:
        _score_and_decide(db, app)


# ---------- VALIDATION ----------
def _validate(db: Session, app: Application) -> None:
    # Для клиентов банка обороты берём из внутренних данных на момент проверки
    if app.company.is_bank_client and (not app.financials or app.financials.get("source") == "BANK_ACCOUNT"):
        fin = bank_financials(db, app.company_inn)
        if fin:
            app.financials = fin

    items = missing_items(
        product_code=app.product_code,
        requires_collateral=app.product.requires_collateral,
        financials=app.financials,
        collateral=app.collateral,
        document_kinds={d.kind for d in app.documents},
    )
    if items:
        app.missing_items = items
        transition(db, app, Status.NEED_INFO, Actor.SYSTEM,
                   reason=" ".join(i["text"] for i in items),
                   payload={"missing_items": items})
    else:
        app.missing_items = None
        transition(db, app, Status.ENRICHMENT, Actor.SYSTEM, reason="Данные полные")


# ---------- ENRICHMENT ----------
def _save_check(db: Session, app: Application, res: CallResult, attempt: int) -> None:
    db.add(ExternalCheck(
        application_id=app.id, source=res.source, status=res.status, attempt=attempt,
        duration_ms=res.duration_ms, response=res.data, error=res.error,
    ))


def _enrich(db: Session, app: Application, client: IntegrationClient) -> None:
    s = get_settings()
    app.enrichment_attempts += 1
    attempt = app.enrichment_attempts

    results = {r.source: r for r in (client.egrul(app.company_inn), client.fns(app.company_inn), client.bki(app.company_inn))}
    for r in results.values():
        _save_check(db, app, r, attempt)

    egrul = results["EGRUL"]
    if egrul.status == "NOT_FOUND":
        app.decision = {
            "outcome": "REJECTED",
            "reasons": [{"impact": "negative", "text": "Компания с таким ИНН не найдена в государственном реестре."}],
            "rules_fired": ["STOP:REGISTRY_NOT_FOUND"],
        }
        transition(db, app, Status.REJECTED, Actor.SYSTEM, reason="Компания не найдена в ЕГРЮЛ/ЕГРИП")
        return
    if egrul.status == "OK" and egrul.data:
        apply_registry_data(app.company, egrul.data)
        if egrul.data.get("status") in STOP_REGISTRY_STATUSES:
            app.decision = {
                "outcome": "REJECTED",
                "reasons": [{"impact": "negative",
                             "text": "По данным реестра компания ликвидирована или находится в процессе ликвидации."}],
                "rules_fired": ["STOP:REGISTRY_STATUS"],
            }
            transition(db, app, Status.REJECTED, Actor.SYSTEM, reason=f"Статус в реестре: {egrul.data.get('status')}")
            return

    failed = [r.source for r in results.values() if r.status == "ERROR"]
    if failed:
        if attempt < s.pipeline_max_enrichment_attempts:
            app.next_action_at = now() + timedelta(seconds=s.pipeline_enrichment_retry_delay_sec * attempt)
            add_event(db, app, "INTEGRATION_RETRY", Actor.SYSTEM,
                      reason=f"Источник недоступен: {', '.join(failed)}. Повтор {attempt + 1}/{s.pipeline_max_enrichment_attempts}",
                      payload={"failed": failed, "attempt": attempt})
            return
        app.decision = {
            "outcome": "MANUAL_REVIEW",
            "recommendation": f"Не удалось получить данные из: {', '.join(failed)} после {attempt} попыток. "
                              "Проверьте источник вручную или запросите документы у клиента.",
            "reasons": [],
            "rules_fired": [f"INTEGRATION_UNAVAILABLE:{','.join(failed)}"],
        }
        transition(db, app, Status.MANUAL_REVIEW, Actor.SYSTEM,
                   reason=f"Внешний источник недоступен ({', '.join(failed)}) — передано специалисту")
        return

    transition(db, app, Status.SCORING, Actor.SYSTEM, reason="Данные из реестров и БКИ получены")


# ---------- SCORING + DECISION ----------
def latest_check(app: Application, source: str) -> dict:
    for c in reversed(app.checks):
        if c.source == source and c.status == "OK":
            return c.response or {}
    return {}


def build_scoring_input(db: Session, app: Application) -> ScoringInput:
    egrul, fns, bki = latest_check(app, "EGRUL"), latest_check(app, "FNS"), latest_check(app, "BKI")
    fin = app.financials or {}
    return ScoringInput(
        business_age_months=months_between(app.company.registered_at) or 0,
        registry_status=egrul.get("status", app.company.registry_status or "ACTIVE"),
        okved=egrul.get("okved", app.company.okved),
        bki_has_history=bool(bki.get("has_history")),
        bki_current_overdue_days=int(bki.get("current_overdue_days", 0)),
        bki_max_overdue_days_12m=int(bki.get("max_overdue_days_12m", 0)),
        bki_monthly_payments=float(bki.get("total_monthly_payments", 0)),
        fns_mass_address=bool(fns.get("mass_address")),
        fns_tax_arrears=float(fns.get("tax_arrears", 0)),
        fns_disqualified_director=bool(fns.get("disqualified_director")),
        avg_monthly_inflow=float(fin.get("avg_monthly_inflow") or 0),
        stability_cv=fin.get("stability_cv"),
        is_bank_client=app.company.is_bank_client,
        bank_history_months=bank_history_months(db, app.company_inn) if app.company.is_bank_client else 0,
    )


def _score_and_decide(db: Session, app: Application) -> None:
    inp = build_scoring_input(db, app)
    result = score(inp)
    product = app.product
    alternatives = [to_terms(p) for p in db.scalars(select(Product).where(Product.is_active)).all()]
    dec = decide(
        to_terms(product),
        result,
        DecisionInput(
            amount=float(app.amount),
            term_months=app.term_months,
            avg_monthly_inflow=inp.avg_monthly_inflow,
            existing_monthly_payments=inp.bki_monthly_payments,
            business_age_months=inp.business_age_months,
            equipment_cost=(app.collateral or {}).get("equipment_cost"),
        ),
        alternatives=alternatives,
    )
    app.score = result.score
    app.score_grade = result.grade
    app.score_details = result.to_dict() | {"input": inp.__dict__}
    app.decision = dec.to_dict() | {"decided_by": "SYSTEM", "decided_at": now().isoformat()}
    transition(db, app, Status(dec.outcome), Actor.SYSTEM,
               reason=f"Скоринг {result.score} ({result.grade}); правила: {', '.join(dec.rules_fired)}",
               payload={"score": result.score, "grade": result.grade, "outcome": dec.outcome})
