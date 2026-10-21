"""Представления заявки для клиента и аналитика.

Клиент видит понятные статусы, решение и причины, но НЕ видит внутренние веса скоринга,
лимиты и сработавшие правила. Аналитик видит всё, включая аудит и ответы источников.
"""
from __future__ import annotations

from app.domain.finance import annuity_payment
from app.domain.purposes import PURPOSES
from app.domain.statuses import CLIENT_COPY, PIPELINE, TERMINAL, Status
from app.models import Application, User
from app.schemas import (
    AnalystApplicationOut,
    ApplicationListItem,
    ApplicationOut,
    CheckOut,
    CompanyOut,
    DocumentOut,
    EventOut,
    FinancialsOut,
    StatusInfo,
    TimelineItem,
    UserOut,
)
from app.services.companies import months_between
from app.services.products import to_out

DECISION_STEP = "DECISION"

UPCOMING = {
    Status.DRAFT: [Status.SUBMITTED, Status.VALIDATION, Status.ENRICHMENT, Status.SCORING, DECISION_STEP, Status.SIGNING, Status.ISSUED],
    Status.SUBMITTED: [Status.VALIDATION, Status.ENRICHMENT, Status.SCORING, DECISION_STEP, Status.SIGNING, Status.ISSUED],
    Status.VALIDATION: [Status.ENRICHMENT, Status.SCORING, DECISION_STEP, Status.SIGNING, Status.ISSUED],
    Status.NEED_INFO: [Status.VALIDATION, Status.ENRICHMENT, Status.SCORING, DECISION_STEP, Status.SIGNING, Status.ISSUED],
    Status.ENRICHMENT: [Status.SCORING, DECISION_STEP, Status.SIGNING, Status.ISSUED],
    Status.SCORING: [DECISION_STEP, Status.SIGNING, Status.ISSUED],
    Status.MANUAL_REVIEW: [DECISION_STEP, Status.SIGNING, Status.ISSUED],
    Status.APPROVED: [Status.SIGNING, Status.ISSUED],
    Status.COUNTER_OFFER: [Status.SIGNING, Status.ISSUED],
    Status.SIGNING: [Status.ISSUED],
}

CLIENT_ACTIONS = {
    Status.DRAFT: ["EDIT", "UPLOAD_DOCUMENT", "SUBMIT", "CANCEL"],
    Status.SUBMITTED: ["CANCEL"],
    Status.NEED_INFO: ["EDIT", "UPLOAD_DOCUMENT", "RESUBMIT", "CANCEL"],
    Status.APPROVED: ["ACCEPT_OFFER", "CANCEL"],
    Status.COUNTER_OFFER: ["ACCEPT_OFFER", "CANCEL"],
    Status.SIGNING: ["SIGN", "CANCEL"],
}
ANALYST_ACTIONS = {Status.MANUAL_REVIEW: ["APPROVE", "COUNTER_OFFER", "REJECT", "REQUEST_INFO"]}


def status_info(status: str) -> StatusInfo:
    c = CLIENT_COPY[Status(status)]
    return StatusInfo(code=status, title=c["title"], what=c["what"], next=c["next"])


def timeline(app: Application) -> list[TimelineItem]:
    items: list[TimelineItem] = []
    changes = [e for e in app.events if e.event_type == "STATUS_CHANGED"]
    for i, e in enumerate(changes):
        last = i == len(changes) - 1
        items.append(TimelineItem(
            status=e.to_status,
            title=CLIENT_COPY[Status(e.to_status)]["title"],
            at=e.created_at,
            state="current" if last and Status(e.to_status) not in TERMINAL else "done",
            actor=e.actor_type,
            reason=e.reason if e.actor_type != "SYSTEM" or e.to_status in ("NEED_INFO", "REJECTED") else None,
        ))
    upcoming = UPCOMING.get(Status(app.status), [])
    if Status(app.status) == Status.NEED_INFO and any(
        item.get("code") == "ANALYST_REQUEST" for item in (app.missing_items or [])
    ):
        upcoming = [Status.MANUAL_REVIEW, DECISION_STEP, Status.SIGNING, Status.ISSUED]
    for st in upcoming:
        title = "Решение банка" if st == DECISION_STEP else CLIENT_COPY[st]["title"]
        items.append(TimelineItem(status=str(st), title=title, at=None, state="upcoming"))
    return items


def client_decision(decision: dict | None) -> dict | None:
    if not decision:
        return None
    return {k: decision.get(k) for k in ("outcome", "offer", "reasons", "decided_by", "decided_at", "analyst_comment", "requested_terms")}


def company_out(app: Application) -> CompanyOut:
    out = CompanyOut.model_validate(app.company)
    out.business_age_months = months_between(app.company.registered_at)
    return out


def _estimate_payment(app: Application) -> float | None:
    try:
        if app.product.rules.get("is_overdraft"):
            return round(float(app.amount) * float(app.product.base_rate) / 100 / 12, 2)
        return round(annuity_payment(float(app.amount), float(app.product.base_rate), app.term_months), 2)
    except (ValueError, ZeroDivisionError):
        return None


def application_out(app: Application) -> ApplicationOut:
    purpose = PURPOSES.get(app.purpose or "")
    return ApplicationOut(
        id=app.id,
        number=app.number,
        version=app.version,
        status=status_info(app.status),
        product=to_out(app.product),
        purpose=app.purpose,
        purpose_title=purpose["title"] if purpose else None,
        purpose_comment=app.purpose_comment,
        amount=float(app.amount),
        term_months=app.term_months,
        estimated_monthly_payment=_estimate_payment(app),
        collateral=app.collateral,
        financials=FinancialsOut(**{k: v for k, v in (app.financials or {}).items() if k in FinancialsOut.model_fields})
        if app.financials
        else None,
        missing_items=app.missing_items,
        analyst_comment=app.analyst_comment,
        decision=client_decision(app.decision),
        agreement=app.agreement,
        timeline=timeline(app),
        documents=[DocumentOut.model_validate(d) for d in app.documents],
        allowed_actions=CLIENT_ACTIONS.get(Status(app.status), []),
        company=company_out(app),
        created_at=app.created_at,
        submitted_at=app.submitted_at,
        status_changed_at=app.status_changed_at,
        processing=Status(app.status) in PIPELINE,
    )


def analyst_application_out(app: Application, users: dict[int, User]) -> AnalystApplicationOut:
    base = application_out(app).model_dump()
    base["decision"] = app.decision
    base["allowed_actions"] = ANALYST_ACTIONS.get(Status(app.status), [])
    events = []
    for e in app.events:
        ev = EventOut.model_validate(e)
        if e.actor_id and e.actor_id in users:
            ev.actor_name = users[e.actor_id].full_name
        elif e.actor_type == "SYSTEM":
            ev.actor_name = "Конвейер"
        events.append(ev)
    return AnalystApplicationOut(
        **base,
        score=app.score,
        score_grade=app.score_grade,
        score_details=app.score_details,
        checks=[CheckOut.model_validate(c) for c in app.checks],
        events=events,
        applicant=UserOut.model_validate(app.applicant),
        assigned_analyst_id=app.assigned_analyst_id,
    )


def list_item(app: Application, with_score: bool = False) -> ApplicationListItem:
    return ApplicationListItem(
        id=app.id,
        number=app.number,
        status=app.status,
        status_title=CLIENT_COPY[Status(app.status)]["title"],
        product_code=app.product_code,
        product_name=app.product.name,
        amount=float(app.amount),
        term_months=app.term_months,
        company_inn=app.company_inn,
        company_name=app.company.name,
        score=app.score if with_score else None,
        score_grade=app.score_grade if with_score else None,
        created_at=app.created_at,
        status_changed_at=app.status_changed_at,
        submitted_at=app.submitted_at,
    )
