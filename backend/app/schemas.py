from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.json_schema import SkipJsonSchema


# ---------- Общие ----------
class ErrorOut(BaseModel):
    error: str
    message: str
    details: Any | None = None
    request_id: str | None = None


# ---------- Auth ----------
class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: Literal["CLIENT", "ANALYST"]
    full_name: str
    position: str | None = None
    company_inn: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DemoAccountOut(BaseModel):
    email: str
    password: str
    role: str
    full_name: str
    company_name: str | None
    scenario: str


# ---------- Компания ----------
class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    inn: str
    name: str
    legal_form: str
    ogrn: str | None
    okved: str | None
    okved_name: str | None
    address: str | None
    director: str | None
    registered_at: date | None
    registry_status: str | None
    is_bank_client: bool
    business_age_months: int | None = None
    registry_synced_at: datetime | None = None


class FinancialsOut(BaseModel):
    source: Literal["BANK_ACCOUNT", "STATEMENT_UPLOAD"] | None = None
    source_label: str | None = None
    months: list[dict] = []
    months_count: int = 0
    avg_monthly_inflow: float | None = None
    annual_revenue_estimate: float | None = None
    stability_cv: float | None = None
    period_from: str | None = None
    period_to: str | None = None


# ---------- Продукты и подбор ----------
class ProductOut(BaseModel):
    code: str
    name: str
    short_description: str
    purposes: list[str]
    min_amount: float
    max_amount: float
    min_term_months: int
    max_term_months: int
    base_rate: float
    requires_collateral: bool
    min_business_age_months: int


class PurposeOut(BaseModel):
    code: str
    title: str
    hint: str
    products: list[str]


class RecommendIn(BaseModel):
    text: str | None = Field(default=None, max_length=1000, description="Свободное описание задачи бизнеса")
    purpose: str | None = Field(default=None, description="Код цели, если выбран явно")


class Recommendation(BaseModel):
    product: ProductOut
    why: str
    rank: int
    estimated_rate_from: float


class RecommendOut(BaseModel):
    purpose: str | None
    purpose_title: str | None
    engine: Literal["rules", "llm"]
    recommendations: list[Recommendation]
    note: str | None = None


# ---------- Заявки ----------
class CollateralIn(BaseModel):
    equipment_name: str | None = Field(default=None, max_length=255)
    equipment_cost: float | None = Field(default=None, gt=0, le=1_000_000_000)
    supplier: str | None = Field(default=None, max_length=255)


class ApplicationCreate(BaseModel):
    product_code: str
    purpose: str | None = None
    purpose_comment: str | None = Field(default=None, max_length=1000)
    amount: float = Field(gt=0, le=1_000_000_000)
    term_months: int = Field(ge=1, le=120)
    collateral: CollateralIn | None = None


class ApplicationUpdate(BaseModel):
    product_code: str | SkipJsonSchema[None] = None
    purpose: str | None = None
    purpose_comment: str | None = Field(default=None, max_length=1000)
    amount: Annotated[float, Field(gt=0, le=1_000_000_000)] | SkipJsonSchema[None] = None
    term_months: Annotated[int, Field(ge=1, le=120)] | SkipJsonSchema[None] = None
    collateral: CollateralIn | None = None
    version: int | None = Field(default=None, description="Для оптимистической блокировки")

    @field_validator('product_code', 'amount', 'term_months', mode='before')
    @classmethod
    def required_values_cannot_be_null(cls, value):
        if value is None:
            raise ValueError('Поле можно пропустить, но нельзя передать null')
        return value


class SubmitIn(BaseModel):
    consent: bool = Field(description="Согласие на обработку данных и запрос в БКИ")

    @field_validator("consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Без согласия на запрос кредитной истории заявку отправить нельзя")
        return v


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class SignIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    confirm: bool
    signer_name: str = Field(min_length=3, max_length=255)


class StatusInfo(BaseModel):
    code: str
    title: str
    what: str
    next: str


class TimelineItem(BaseModel):
    status: str
    title: str
    at: datetime | None
    state: Literal["done", "current", "upcoming", "skipped"]
    actor: str | None = None
    reason: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    filename: str
    content_type: str
    size_bytes: int
    parsed: dict | None = None
    created_at: datetime


class ApplicationListItem(BaseModel):
    id: int
    number: str
    status: str
    status_title: str
    product_code: str
    product_name: str
    amount: float
    term_months: int
    company_inn: str
    company_name: str
    score: int | None = None
    score_grade: str | None = None
    created_at: datetime
    status_changed_at: datetime
    submitted_at: datetime | None = None


class AnalystQueuePageOut(BaseModel):
    items: list[ApplicationListItem]
    total: int
    limit: int
    offset: int


class ApplicationOut(BaseModel):
    id: int
    number: str
    version: int
    status: StatusInfo
    product: ProductOut
    purpose: str | None
    purpose_title: str | None
    purpose_comment: str | None
    amount: float
    term_months: int
    estimated_monthly_payment: float | None
    collateral: dict | None
    financials: FinancialsOut | None
    missing_items: list[dict] | None
    analyst_comment: str | None
    decision: dict | None
    agreement: dict | None
    timeline: list[TimelineItem]
    documents: list[DocumentOut]
    allowed_actions: list[str]
    company: CompanyOut
    created_at: datetime
    submitted_at: datetime | None
    status_changed_at: datetime
    processing: bool = Field(description="Заявка сейчас обрабатывается конвейером — интерфейс опрашивает статус")


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    from_status: str | None
    to_status: str | None
    actor_type: str
    actor_id: int | None
    actor_name: str | None = None
    reason: str | None
    payload: dict | None
    created_at: datetime


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    status: str
    attempt: int
    duration_ms: int | None
    response: dict | None
    error: str | None
    created_at: datetime


class AnalystApplicationOut(ApplicationOut):
    score: int | None
    score_grade: str | None
    score_details: dict | None
    checks: list[CheckOut]
    events: list[EventOut]
    applicant: UserOut
    assigned_analyst_id: int | None


class AnalystDecisionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    action: Literal["APPROVE", "COUNTER_OFFER", "REJECT", "REQUEST_INFO"]
    version: int = Field(description="Версия заявки, которую видел аналитик (оптимистическая блокировка)")
    amount: float | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, ge=1, le=120)
    rate: float | None = Field(default=None, gt=0, lt=100)
    product_code: str | None = None
    comment: str = Field(min_length=3, max_length=2000, description="Обоснование решения — попадает в аудит")
    requested_items: list[str] | None = Field(default=None, description="Для REQUEST_INFO: что запросить у клиента")


# ---------- Уведомления ----------
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int | None
    title: str
    body: str
    is_read: bool
    created_at: datetime


class NotificationsOut(BaseModel):
    unread: int
    items: list[NotificationOut]


class StatsOut(BaseModel):
    by_status: dict[str, int]
    total: int
    in_review: int
    approval_rate: float | None
    avg_decision_seconds: float | None
