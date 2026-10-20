"""HTTP API. Контракт генерируется в OpenAPI (/api/docs, /api/openapi.json)."""
from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.domain.purposes import PURPOSES
from app.domain.statuses import Status
from app.errors import DomainError, not_found
from app.integrations.client import IntegrationClient
from app.models import Application, ApplicationEvent, Company, Document, Notification, User
from app.schemas import (
    AnalystApplicationOut,
    AnalystDecisionIn,
    ApplicationCreate,
    ApplicationListItem,
    ApplicationOut,
    ApplicationUpdate,
    CancelIn,
    CompanyOut,
    DemoAccountOut,
    ErrorOut,
    FinancialsOut,
    LoginIn,
    NotificationsOut,
    ProductOut,
    PurposeOut,
    RecommendIn,
    RecommendOut,
    SignIn,
    StatsOut,
    SubmitIn,
    TokenOut,
    UserOut,
)
from app.security import create_token, get_current_user, require_analyst, require_client, verify_password
from app.services import applications as svc
from app.services.assistant import recommend
from app.services.companies import bank_financials, months_between, sync_company
from app.services.products import list_products, to_out
from app.services.views import analyst_application_out, application_out, list_item

ERRORS = {400: {"model": ErrorOut}, 401: {"model": ErrorOut}, 403: {"model": ErrorOut},
          404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 422: {"model": ErrorOut}}

DbDep = Annotated[Session, Depends(get_db)]
ClientDep = Annotated[User, Depends(require_client)]
AnalystDep = Annotated[User, Depends(require_analyst)]

# ---------------- Health ----------------
health = APIRouter(tags=["health"])


@health.get("/health/live", summary="Liveness-проба")
def live() -> dict:
    return {"status": "ok"}


@health.get("/health/ready", summary="Readiness-проба: БД и внешние интеграции")
def ready(db: DbDep, response: Response) -> dict:
    checks = {}
    try:
        db.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["database"] = f"error: {type(e).__name__}"
    try:
        import httpx

        r = httpx.get(f"{get_settings().mocks_base_url}/health", timeout=1.0)
        checks["integrations"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
    except Exception as e:  # noqa: BLE001
        checks["integrations"] = f"degraded: {type(e).__name__}"
    ok = checks["database"] == "ok"
    response.status_code = 200 if ok else 503
    return {"status": "ok" if ok else "unavailable", "checks": checks}


api = APIRouter(prefix="/api", responses=ERRORS)

# ---------------- Auth ----------------
DEMO_SCENARIOS = {
    "anna@demo.ru": "Идеальный клиент банка → автоматическое одобрение",
    "start@demo.ru": "Молодой IT-бизнес, просит больше, чем позволяет выручка → контрпредложение",
    "kovalev@demo.ru": "Не клиент банка, кредит на оборудование → дозапрос выписки и счёта → одобрение",
    "sever@demo.ru": "Пограничный балл → ручное рассмотрение аналитиком",
    "vector@demo.ru": "Текущая просрочка 47 дней в БКИ → отказ (стоп-фактор)",
    "zakat@demo.ru": "Компания ликвидирована по данным ЕГРЮЛ → отказ на этапе проверки",
    "tikhonova@demo.ru": "БКИ недоступно → ретраи → передача специалисту",
    "analyst@demo.ru": "Кредитный аналитик: очередь и ручное рассмотрение",
}


@api.post("/auth/login", response_model=TokenOut, tags=["auth"], summary="Вход по email и паролю")
def login(data: LoginIn, db: DbDep) -> TokenOut:
    user = db.scalars(select(User).where(User.email == data.email.lower().strip())).first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise DomainError("INVALID_CREDENTIALS", "Неверный email или пароль", 401)
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@api.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(user)


@api.get("/auth/demo-accounts", response_model=list[DemoAccountOut], tags=["auth"],
         summary="Тестовые учётки для проверки (отключается при ENVIRONMENT=production)")
def demo_accounts(db: DbDep) -> list[DemoAccountOut]:
    if get_settings().environment == "production":
        return []
    users = db.scalars(select(User).order_by(User.role.desc(), User.id)).all()
    return [
        DemoAccountOut(email=u.email, password="demo2026", role=u.role, full_name=u.full_name,
                       company_name=u.company.name if u.company else None, scenario=DEMO_SCENARIOS.get(u.email, ""))
        for u in users if u.email in DEMO_SCENARIOS
    ]


# ---------------- Компания клиента ----------------
@api.get("/companies/me", response_model=CompanyOut, tags=["company"],
         summary="Карточка компании: реквизиты подтягиваются из реестра по ИНН")
def my_company(user: ClientDep, db: DbDep) -> CompanyOut:
    company = db.get(Company, user.company_inn)
    if company is None:
        raise not_found("Компания")
    if sync_company(db, company):
        db.commit()
    out = CompanyOut.model_validate(company)
    out.business_age_months = months_between(company.registered_at)
    return out


@api.get("/companies/me/financials", response_model=FinancialsOut | None, tags=["company"],
         summary="Обороты по счёту в банке (если компания — клиент банка)")
def my_financials(user: ClientDep, db: DbDep):
    fin = bank_financials(db, user.company_inn)
    return FinancialsOut(**{k: v for k, v in fin.items() if k in FinancialsOut.model_fields}) if fin else None


# ---------------- Продукты и подбор ----------------
@api.get("/products", response_model=list[ProductOut], tags=["products"])
def products(db: DbDep) -> list[ProductOut]:
    return [to_out(p) for p in list_products(db)]


@api.get("/products/purposes", response_model=list[PurposeOut], tags=["products"],
         summary="Цели финансирования для подбора продукта «по задаче»")
def purposes() -> list[PurposeOut]:
    return [PurposeOut(code=k, title=v["title"], hint=v["hint"], products=v["products"]) for k, v in PURPOSES.items()]


@api.post("/assistant/recommend", response_model=RecommendOut, tags=["products"],
          summary="Подбор продукта по цели или свободному описанию задачи")
def assistant_recommend(data: RecommendIn, db: DbDep, _: Annotated[User, Depends(get_current_user)]) -> RecommendOut:
    return recommend(db, data.text, data.purpose)


# ---------------- Заявки: клиент ----------------
@api.get("/applications", response_model=list[ApplicationListItem], tags=["client-applications"])
def my_applications(user: ClientDep, db: DbDep) -> list[ApplicationListItem]:
    apps = db.scalars(
        select(Application).where(Application.company_inn == user.company_inn).order_by(Application.id.desc())
    ).all()
    return [list_item(a) for a in apps]


@api.post("/applications", response_model=ApplicationOut, status_code=201, tags=["client-applications"],
          summary="Создать черновик заявки (идемпотентно по заголовку Idempotency-Key)")
def create_application(
    data: ApplicationCreate, user: ClientDep, db: DbDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=64)] = None,
) -> ApplicationOut:
    return application_out(svc.create_application(db, user, data, idempotency_key))


@api.get("/applications/{app_id}", response_model=ApplicationOut, tags=["client-applications"])
def get_application(app_id: int, user: ClientDep, db: DbDep) -> ApplicationOut:
    return application_out(svc.get_client_app(db, user, app_id))


@api.patch("/applications/{app_id}", response_model=ApplicationOut, tags=["client-applications"],
           summary="Изменить черновик или дополнить заявку по запросу банка")
def update_application(app_id: int, data: ApplicationUpdate, user: ClientDep, db: DbDep) -> ApplicationOut:
    return application_out(svc.update_application(db, user, app_id, data))


@api.post("/applications/{app_id}/submit", response_model=ApplicationOut, tags=["client-applications"],
          summary="Отправить заявку в банк (DRAFT → SUBMITTED). Идемпотентно.")
def submit_application(app_id: int, data: SubmitIn, user: ClientDep, db: DbDep) -> ApplicationOut:
    return application_out(svc.submit(db, user, app_id))


@api.post("/applications/{app_id}/resubmit", response_model=ApplicationOut, tags=["client-applications"],
          summary="Отправить дополненную заявку (NEED_INFO → VALIDATION)")
def resubmit_application(app_id: int, user: ClientDep, db: DbDep) -> ApplicationOut:
    return application_out(svc.resubmit(db, user, app_id))


@api.post("/applications/{app_id}/cancel", response_model=ApplicationOut, tags=["client-applications"])
def cancel_application(app_id: int, data: CancelIn, user: ClientDep, db: DbDep) -> ApplicationOut:
    return application_out(svc.cancel(db, user, app_id, data.reason))


@api.post("/applications/{app_id}/accept", response_model=ApplicationOut, tags=["client-applications"],
          summary="Принять предложение банка → формирование договора (SIGNING)")
def accept_offer(app_id: int, user: ClientDep, db: DbDep) -> ApplicationOut:
    return application_out(svc.accept_offer(db, user, app_id))


@api.post("/applications/{app_id}/sign", response_model=ApplicationOut, tags=["client-applications"],
          summary="Подписать договор (симуляция ПЭП) и получить средства (симуляция)")
def sign_agreement(app_id: int, data: SignIn, user: ClientDep, db: DbDep) -> ApplicationOut:
    if not data.confirm:
        raise DomainError("CONFIRM_REQUIRED", "Подтвердите согласие с условиями договора", 422)
    return application_out(svc.sign(db, user, app_id, data.signer_name))


@api.post("/applications/{app_id}/documents", response_model=ApplicationOut, status_code=201,
          tags=["client-applications"],
          summary="Загрузить документ. Выписка (STATEMENT, CSV) распознаётся автоматически в помесячные обороты.")
async def upload_document(
    app_id: int, user: ClientDep, db: DbDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form(description="STATEMENT | EQUIPMENT_INVOICE | OTHER")] = "OTHER",
) -> ApplicationOut:
    content = await file.read(get_settings().max_upload_bytes + 1)
    app, _ = svc.upload_document(db, user, app_id, kind, file.filename or "file", file.content_type, content)
    return application_out(app)


def _doc_response(doc: Document) -> Response:
    return Response(
        content=doc.content, media_type=doc.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.filename)}"},
    )


@api.get("/applications/{app_id}/documents/{doc_id}", tags=["client-applications"], response_class=Response)
def download_document(app_id: int, doc_id: int, user: ClientDep, db: DbDep) -> Response:
    app = svc.get_client_app(db, user, app_id)
    doc = next((d for d in app.documents if d.id == doc_id), None)
    if doc is None:
        raise not_found("Документ")
    return _doc_response(doc)


# ---------------- Аналитик ----------------
@api.get("/analyst/applications", response_model=list[ApplicationListItem], tags=["analyst"],
         summary="Очередь заявок с фильтрами")
def analyst_queue(
    _: AnalystDep, db: DbDep,
    status: Annotated[list[str] | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100, description="Поиск по номеру, ИНН, названию")] = None,
) -> list[ApplicationListItem]:
    stmt = select(Application).join(Company).where(Application.status != Status.DRAFT.value)
    if status:
        stmt = stmt.where(Application.status.in_(status))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Application.number.ilike(like) | Company.inn.ilike(like) | Company.name.ilike(like))
    apps = db.scalars(stmt.order_by(Application.status_changed_at.desc()).limit(200)).all()
    return [list_item(a, with_score=True) for a in apps]


@api.get("/analyst/applications/{app_id}", response_model=AnalystApplicationOut, tags=["analyst"],
         summary="Полная карточка заявки: проверки, скоринг, аудит")
def analyst_application(app_id: int, _: AnalystDep, db: DbDep) -> AnalystApplicationOut:
    app = svc.get_app(db, app_id)
    ids = {e.actor_id for e in app.events if e.actor_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    return analyst_application_out(app, users)


@api.post("/analyst/applications/{app_id}/decision", response_model=AnalystApplicationOut, tags=["analyst"],
          summary="Решение аналитика по заявке на ручном рассмотрении")
def analyst_decision(app_id: int, data: AnalystDecisionIn, analyst: AnalystDep, db: DbDep) -> AnalystApplicationOut:
    svc.analyst_decide(db, analyst, app_id, data)
    return analyst_application(app_id, analyst, db)


@api.get("/analyst/applications/{app_id}/documents/{doc_id}", tags=["analyst"], response_class=Response)
def analyst_download(app_id: int, doc_id: int, _: AnalystDep, db: DbDep) -> Response:
    doc = db.get(Document, doc_id)
    if doc is None or doc.application_id != app_id:
        raise not_found("Документ")
    return _doc_response(doc)


@api.get("/analyst/stats", response_model=StatsOut, tags=["analyst"], summary="Сводка по конвейеру")
def analyst_stats(_: AnalystDep, db: DbDep) -> StatsOut:
    rows = db.execute(select(Application.status, func.count()).group_by(Application.status)).all()
    by_status = {s: n for s, n in rows}
    decided = sum(by_status.get(s, 0) for s in ("APPROVED", "COUNTER_OFFER", "SIGNING", "ISSUED", "REJECTED"))
    positive = decided - by_status.get("REJECTED", 0)
    # среднее время от отправки до первого решения
    first_decision = (
        select(ApplicationEvent.application_id, func.min(ApplicationEvent.created_at).label("at"))
        .where(ApplicationEvent.to_status.in_(["APPROVED", "COUNTER_OFFER", "REJECTED", "MANUAL_REVIEW"]))
        .group_by(ApplicationEvent.application_id)
        .subquery()
    )
    avg = db.execute(
        select(func.avg(func.extract("epoch", first_decision.c.at - Application.submitted_at)))
        .join(first_decision, first_decision.c.application_id == Application.id)
    ).scalar()
    return StatsOut(
        by_status=by_status,
        total=sum(by_status.values()),
        in_review=by_status.get("MANUAL_REVIEW", 0),
        approval_rate=round(positive / decided, 3) if decided else None,
        avg_decision_seconds=round(float(avg), 1) if avg is not None else None,
    )


# ---------------- Уведомления ----------------
@api.get("/notifications", response_model=NotificationsOut, tags=["notifications"],
         summary="Уведомления внутри кабинета")
def notifications(user: Annotated[User, Depends(get_current_user)], db: DbDep) -> NotificationsOut:
    items = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(50)
    ).all()
    unread = db.scalar(select(func.count()).where(Notification.user_id == user.id, ~Notification.is_read))
    return NotificationsOut(unread=unread or 0, items=items)


@api.post("/notifications/read-all", status_code=204, tags=["notifications"])
def read_all(user: Annotated[User, Depends(get_current_user)], db: DbDep) -> Response:
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, ~Notification.is_read)):
        n.is_read = True
    db.commit()
    return Response(status_code=204)


@api.get("/integrations/status", tags=["health"], summary="Доступность моков внешних источников")
def integrations_status(_: Annotated[User, Depends(get_current_user)]) -> dict:
    c = IntegrationClient()
    c.retries = 1
    res = c.egrul("0000000000")
    return {"mocks_base_url": c.base_url, "reachable": res.status in ("OK", "NOT_FOUND")}
