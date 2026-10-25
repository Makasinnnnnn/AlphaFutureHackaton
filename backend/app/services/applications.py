"""Действия клиента и аналитика над заявкой."""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.domain.decision import rate_for, monthly_load, max_amount_for_term, DecisionInput
from app.domain.statement_history import contiguous_tail
from app.domain.finance import annuity_payment, overdraft_monthly_cost, payment_schedule
from app.domain.purposes import PURPOSES
from app.domain.statement_parser import StatementParseError, parse_statement
from app.domain.statuses import EDITABLE_BY_CLIENT, Actor, Status
from app.errors import DomainError, conflict, not_found
from app.models import Application, Document, Product, User
from app.schemas import AnalystDecisionIn, ApplicationCreate, ApplicationUpdate
from app.services.companies import bank_financials, build_financials
from app.services.products import to_terms
from app.services.request_documents import can_resubmit, request_items
from app.services.workflow import add_event, now, transition

ALLOWED_DOC_KINDS = {"STATEMENT", "EQUIPMENT_INVOICE", "OTHER"}
ALLOWED_CONTENT_TYPES = {
    "text/csv", "application/vnd.ms-excel", "text/plain", "application/pdf",
    "image/png", "image/jpeg", "application/octet-stream",
}

APP_LOAD = (
    selectinload(Application.events),
    selectinload(Application.checks),
    selectinload(Application.documents),
    selectinload(Application.company),
    selectinload(Application.product),
    selectinload(Application.applicant),
)


def get_app(db: Session, app_id: int, *, for_update: bool = False) -> Application:
    db.expire_all()  # всегда читаем актуальное состояние заявки и связанных записей
    q = (select(Application).where(Application.id == app_id).options(*APP_LOAD)
         .execution_options(populate_existing=True))
    if for_update:
        q = q.with_for_update(of=Application)
    app = db.scalars(q).first()
    if app is None:
        raise not_found("Заявка")
    return app


def get_client_app(db: Session, user: User, app_id: int, *, for_update: bool = False) -> Application:
    app = get_app(db, app_id, for_update=for_update)
    if app.company_inn != user.company_inn:
        raise not_found("Заявка")  # не раскрываем существование чужих заявок
    return app


def _product(db: Session, code: str) -> Product:
    p = db.get(Product, code)
    if p is None or not p.is_active:
        raise DomainError("UNKNOWN_PRODUCT", "Такого продукта нет", 422)
    return p


def _check_params(p: Product, amount: float, term: int) -> None:
    errors = []
    if not float(p.min_amount) <= amount <= float(p.max_amount):
        errors.append(f"Сумма должна быть от {float(p.min_amount):,.0f} до {float(p.max_amount):,.0f} ₽".replace(",", " "))
    if not p.min_term_months <= term <= p.max_term_months:
        errors.append(f"Срок должен быть от {p.min_term_months} до {p.max_term_months} мес.")
    if errors:
        raise DomainError("INVALID_PARAMS", "; ".join(errors), 422, errors)


def _check_version(app: Application, version: int | None) -> None:
    if version is not None and version != app.version:
        raise conflict("Заявка была изменена — обновите страницу.", {"current_version": app.version})


# ---------------- Клиент ----------------
def create_application(db: Session, user: User, data: ApplicationCreate, idempotency_key: str | None) -> Application:
    if idempotency_key:
        # Serialize duplicate requests before checking/inserting. The unique constraint
        # alone converts simultaneous retries into an unhandled IntegrityError.
        db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(
            f'application:{user.id}:{idempotency_key}', 0))))
        existing = db.scalars(
            select(Application).where(Application.applicant_id == user.id, Application.idempotency_key == idempotency_key)
        ).first()
        if existing:
            return get_app(db, existing.id)

    p = _product(db, data.product_code)
    _check_params(p, data.amount, data.term_months)
    if data.purpose and data.purpose not in PURPOSES:
        raise DomainError("UNKNOWN_PURPOSE", "Неизвестная цель финансирования", 422)

    app = Application(
        number=f"TMP-{uuid.uuid4().hex[:12]}",
        company_inn=user.company_inn,
        applicant_id=user.id,
        product_code=p.code,
        purpose=data.purpose,
        purpose_comment=data.purpose_comment,
        amount=data.amount,
        term_months=data.term_months,
        collateral=data.collateral.model_dump(exclude_none=True) if data.collateral else None,
        status=Status.DRAFT.value,
        idempotency_key=idempotency_key,
    )
    # Не просим клиента банка вводить обороты — подставляем из внутренних данных
    app.financials = bank_financials(db, user.company_inn)
    db.add(app)
    db.flush()
    app.number = f"CR-{datetime.now(UTC).year}-{app.id:06d}"
    add_event(db, app, "STATUS_CHANGED", Actor.CLIENT, user.id, "Черновик создан", to_status=Status.DRAFT.value)
    db.commit()
    return get_app(db, app.id)


def update_application(db: Session, user: User, app_id: int, data: ApplicationUpdate) -> Application:
    app = get_client_app(db, user, app_id, for_update=True)
    _check_version(app, data.version)
    if Status(app.status) not in EDITABLE_BY_CLIENT:
        raise conflict("Заявку в текущем статусе изменить нельзя.")
    fields = data.model_dump(exclude_unset=True, exclude={"version"})
    if fields.get('purpose') is not None and fields['purpose'] not in PURPOSES:
        raise DomainError('UNKNOWN_PURPOSE', 'Неизвестная цель финансирования', 422)
    if Status(app.status) == Status.NEED_INFO:
        # после отправки нельзя менять продукт/сумму/срок — только дополнять данные
        locked = {"product_code", "amount", "term_months"} & fields.keys()
        if locked:
            raise conflict("На этапе дозапроса можно только дополнить данные, а не менять условия.")
    if "product_code" in fields:
        p = _product(db, fields["product_code"])
        app.product_code = p.code
        app.product = p
    for k in ("purpose", "purpose_comment", "amount", "term_months"):
        if k in fields:
            setattr(app, k, fields[k])
    if "collateral" in fields:
        app.collateral = data.collateral.model_dump(exclude_none=True) if data.collateral else None
    _check_params(app.product, float(app.amount), app.term_months)
    add_event(db, app, "UPDATED", Actor.CLIENT, user.id, payload={"fields": sorted(fields.keys())})
    db.commit()
    return get_app(db, app.id)


def submit(db: Session, user: User, app_id: int) -> Application:
    app = get_client_app(db, user, app_id, for_update=True)
    if Status(app.status) != Status.DRAFT:
        if app.submitted_at:  # повторная отправка — идемпотентно
            return app
        raise conflict("Отправить можно только черновик.")
    _check_params(app.product, float(app.amount), app.term_months)
    app.submitted_at = now()
    app.consent_given_at = now()
    transition(db, app, Status.SUBMITTED, Actor.CLIENT, user.id, reason="Клиент отправил заявку")
    db.commit()
    return get_app(db, app.id)


def resubmit(db: Session, user: User, app_id: int) -> Application:
    app = get_client_app(db, user, app_id, for_update=True)
    if Status(app.status) != Status.NEED_INFO:
        raise conflict("Повторно отправить можно только заявку, по которой запрошены данные.")
    if not can_resubmit(app):
        raise conflict("Дополните все запрошенные данные и приложите актуальные документы перед повторной отправкой.")
    requests = [i for i in (request_items(app) or []) if i.get("code") == "ANALYST_REQUEST"]
    if requests:
        app.missing_items = None
        transition(db, app, Status.MANUAL_REVIEW, Actor.CLIENT, user.id,
                   reason="Клиент приложил документы; специалист проверит ответ на дозапрос",
                   payload={"fulfilled_requests": requests, "document_ids": [d.id for d in app.documents]})
        db.commit()
        return get_app(db, app.id)
    transition(db, app, Status.VALIDATION, Actor.CLIENT, user.id, reason="Клиент дополнил данные")
    db.commit()
    return get_app(db, app.id)


def cancel(db: Session, user: User, app_id: int, reason: str | None) -> Application:
    app = get_client_app(db, user, app_id, for_update=True)
    transition(db, app, Status.CANCELLED, Actor.CLIENT, user.id, reason=reason or "Отменено клиентом")
    db.commit()
    return get_app(db, app.id)


def accept_offer(db: Session, user: User, app_id: int) -> Application:
    app = get_client_app(db, user, app_id, for_update=True)
    if Status(app.status) not in (Status.APPROVED, Status.COUNTER_OFFER):
        raise conflict("Нет активного предложения банка.")
    offer = (app.decision or {}).get("offer")
    if not offer:
        raise conflict("В решении нет условий для подписания.")
    start = now().date()
    is_od = offer["product_code"] == "OVERDRAFT"
    schedule = [] if is_od else payment_schedule(offer["amount"], offer["rate"], offer["term_months"], start)
    app.agreement = {
        "number": f"КД-{app.number}",
        "product_code": offer["product_code"],
        "product_name": offer["product_name"],
        "amount": offer["amount"],
        "term_months": offer["term_months"],
        "rate": offer["rate"],
        "monthly_payment": offer["monthly_payment"],
        "total_payments": round(sum(r["payment"] for r in schedule), 2) if schedule else None,
        "overpayment": round(sum(r["interest"] for r in schedule), 2) if schedule else None,
        "schedule": schedule,
        "borrower": {"name": app.company.name, "inn": app.company.inn, "ogrn": app.company.ogrn,
                     "director": app.company.director},
        "created_at": now().isoformat(),
        "signed_at": None,
    }
    transition(db, app, Status.SIGNING, Actor.CLIENT, user.id, reason="Клиент принял предложение",
               payload={"offer": offer})
    db.commit()
    return get_app(db, app.id)


def sign(db: Session, user: User, app_id: int, signer_name: str) -> Application:
    """Симуляция подписания (ПЭП в кабинете) и выдачи средств — без реальных операций."""
    app = get_client_app(db, user, app_id, for_update=True)
    if Status(app.status) != Status.SIGNING or not app.agreement:
        raise conflict("Договор не готов к подписанию.")
    ag = dict(app.agreement)
    terms = {k: ag[k] for k in ("number", "amount", "term_months", "rate", "product_code")}
    ag["signed_at"] = now().isoformat()
    ag["signer"] = {"user_id": user.id, "name": signer_name}
    ag["signature"] = {
        "type": "SIMULATED_SIMPLE_E_SIGNATURE",
        "document_hash": hashlib.sha256(repr(sorted(terms.items())).encode()).hexdigest(),
    }
    ag["disbursement"] = {
        "status": "SIMULATED",
        "amount": ag["amount"],
        "account": "40702810" + app.company_inn[-10:].rjust(12, "0"),
        "at": now().isoformat(),
    }
    app.agreement = ag
    transition(db, app, Status.ISSUED, Actor.CLIENT, user.id, reason="Договор подписан, средства зачислены (симуляция)")
    db.commit()
    return get_app(db, app.id)


def upload_document(db: Session, user: User, app_id: int, kind: str, filename: str,
                    content_type: str | None, content: bytes) -> tuple[Application, Document]:
    s = get_settings()
    app = get_client_app(db, user, app_id, for_update=True)
    if Status(app.status) not in EDITABLE_BY_CLIENT:
        raise conflict("Документы можно добавлять только в черновик или по запросу банка.")
    if kind not in ALLOWED_DOC_KINDS:
        raise DomainError("INVALID_KIND", "Неизвестный тип документа", 422)
    if not content:
        raise DomainError("EMPTY_FILE", "Файл пустой", 422)
    if len(content) > s.max_upload_bytes:
        raise DomainError("FILE_TOO_LARGE", f"Файл больше {s.max_upload_bytes // 1024 // 1024} МБ", 413)
    ctype = (content_type or "application/octet-stream").split(";")[0]
    if ctype not in ALLOWED_CONTENT_TYPES:
        raise DomainError("INVALID_TYPE", "Поддерживаются CSV, PDF, PNG, JPEG", 415)

    parsed = None
    if kind == "STATEMENT":
        try:
            parsed = parse_statement(content)
        except StatementParseError as e:
            raise DomainError("STATEMENT_PARSE_ERROR", str(e), 422) from e
        # распознанная выписка заменяет ручной ввод оборотов
        months = contiguous_tail(parsed["months"])[-6:]
        app.financials = build_financials("STATEMENT_UPLOAD", [
            {"month": m["month"], "inflow": m["inflow"], "outflow": m["outflow"]} for m in months
        ])

    doc = Document(
        application_id=app.id, kind=kind, filename=filename[:255], content_type=ctype,
        size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), content=content,
        parsed=parsed, uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()
    add_event(db, app, "DOCUMENT_UPLOADED", Actor.CLIENT, user.id,
              payload={"document_id": doc.id, "kind": kind, "filename": doc.filename})
    db.commit()
    return get_app(db, app.id), doc


# ---------------- Аналитик ----------------
def analyst_decide(db: Session, analyst: User, app_id: int, data: AnalystDecisionIn) -> Application:
    app = get_app(db, app_id, for_update=True)
    _check_version(app, data.version)
    if Status(app.status) != Status.MANUAL_REVIEW:
        raise conflict("Решение аналитика доступно только для заявок на ручном рассмотрении.")

    prev = dict(app.decision or {})
    proposed = prev.get("offer") or {}
    base = {
        "decided_by": "ANALYST",
        "analyst_id": analyst.id,
        "analyst_name": analyst.full_name,
        "decided_at": now().isoformat(),
        "analyst_comment": data.comment,
        "system_decision": {k: prev.get(k) for k in ("outcome", "offer", "recommendation", "rules_fired")},
    }
    app.assigned_analyst_id = analyst.id
    app.analyst_comment = data.comment

    if data.action in ("APPROVE", "COUNTER_OFFER"):
        product = _product(db, data.product_code or proposed.get("product_code") or app.product_code)
        amount = round(float(data.amount or proposed.get("amount") or app.amount), 2)
        term = data.term_months or proposed.get("term_months") or app.term_months
        _check_params(product, float(amount), int(term))
        rate = data.rate or proposed.get("rate") or rate_for(to_terms(product), app.score_grade or "C")
        payment = overdraft_monthly_cost(amount, rate) if product.rules.get("is_overdraft") \
            else annuity_payment(float(amount), float(rate), int(term))
        offer = {"product_code": product.code, "product_name": product.name, "amount": amount,
                 "term_months": int(term), "rate": float(rate), "monthly_payment": round(payment, 2)}
        changed_terms = product.code != app.product_code or amount != float(app.amount) or int(term) != app.term_months
        outcome = Status.COUNTER_OFFER if data.action == "COUNTER_OFFER" or changed_terms else Status.APPROVED
        original_product = to_terms(app.product)
        original_rate = (prev.get("requested_terms") or {}).get("rate") or rate_for(original_product, app.score_grade or "C")
        requested_terms = {"rate": original_rate, "is_overdraft": original_product.is_overdraft,
                           "monthly_payment": round(monthly_load(original_product, float(app.amount), original_rate, app.term_months), 2)}
        from app.services.pipeline import build_scoring_input
        profile = build_scoring_input(db, app)
        limits_input = DecisionInput(float(app.amount), app.term_months, profile.avg_monthly_inflow,
                                     profile.bki_monthly_payments, profile.business_age_months,
                                     (app.collateral or {}).get("equipment_cost"))
        _, original_limits = max_amount_for_term(original_product, limits_input, original_rate, app.term_months)
        _, offer_limits = max_amount_for_term(to_terms(product), limits_input, rate, int(term))
        app.decision = base | {"outcome": outcome.value, "offer": offer,
                               "requested_terms": requested_terms,
                               "limits": original_limits, "offer_limits": offer_limits,
                               "reasons": [{"impact": "neutral", "text": data.comment}] + (prev.get("reasons") or [])}
        transition(db, app, outcome, Actor.ANALYST, analyst.id, reason=data.comment, payload={"offer": offer})
    elif data.action == "REJECT":
        app.decision = base | {"outcome": "REJECTED", "offer": None,
                               "reasons": [{"impact": "negative", "text": data.comment}] + (prev.get("reasons") or [])}
        transition(db, app, Status.REJECTED, Actor.ANALYST, analyst.id, reason=data.comment)
    else:  # REQUEST_INFO
        items = [{"code": "ANALYST_REQUEST", "text": t} for t in (data.requested_items or []) if t.strip()]
        if not items:
            items = [{"code": "ANALYST_REQUEST", "text": data.comment}]
        for item in items:
            item["document_ids_before_request"] = [d.id for d in app.documents]
        app.missing_items = items
        app.decision = prev | {"analyst_comment": data.comment}
        transition(db, app, Status.NEED_INFO, Actor.ANALYST, analyst.id, reason=data.comment,
                   payload={"missing_items": items})
    db.commit()
    return get_app(db, app.id)
