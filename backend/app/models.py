from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))  # CLIENT | ANALYST
    full_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[str | None] = mapped_column(String(255))
    company_inn: Mapped[str | None] = mapped_column(String(12), ForeignKey("companies.inn"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped["Company | None"] = relationship()


class Company(Base):
    """Карточка клиента. Реквизиты подтягиваются из реестра (мок ЕГРЮЛ/ЕГРИП) по ИНН."""

    __tablename__ = "companies"

    inn: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    legal_form: Mapped[str] = mapped_column(String(8))  # IP | OOO
    ogrn: Mapped[str | None] = mapped_column(String(15))
    okved: Mapped[str | None] = mapped_column(String(16))
    okved_name: Mapped[str | None] = mapped_column(String(500))
    address: Mapped[str | None] = mapped_column(String(500))
    director: Mapped[str | None] = mapped_column(String(255))
    registered_at: Mapped[date | None] = mapped_column(Date)
    registry_status: Mapped[str | None] = mapped_column(String(32))
    is_bank_client: Mapped[bool] = mapped_column(Boolean, default=False)
    registry_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountTurnover(Base):
    """Внутренние данные банка: обороты по расчётному счёту клиента (синтетика)."""

    __tablename__ = "account_turnovers"
    __table_args__ = (UniqueConstraint("company_inn", "month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_inn: Mapped[str] = mapped_column(String(12), ForeignKey("companies.inn"), index=True)
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    inflow: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    outflow: Mapped[Decimal] = mapped_column(Numeric(18, 2))


class Product(Base):
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    short_description: Mapped[str] = mapped_column(Text)
    purposes: Mapped[list] = mapped_column(JsonType)  # цели, под которые подходит продукт
    min_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    min_term_months: Mapped[int] = mapped_column(Integer)
    max_term_months: Mapped[int] = mapped_column(Integer)
    base_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # % годовых
    requires_collateral: Mapped[bool] = mapped_column(Boolean, default=False)
    rules: Mapped[dict] = mapped_column(JsonType)  # пороги кредитного решения
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("applicant_id", "idempotency_key", name="uq_application_idempotency"),
        Index("ix_applications_pipeline", "status", "next_action_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    company_inn: Mapped[str] = mapped_column(String(12), ForeignKey("companies.inn"), index=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code"))
    purpose: Mapped[str | None] = mapped_column(String(32))
    purpose_comment: Mapped[str | None] = mapped_column(Text)

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    collateral: Mapped[dict | None] = mapped_column(JsonType)  # для кредита на оборудование
    financials: Mapped[dict | None] = mapped_column(JsonType)  # обороты: источник + помесячно

    status: Mapped[str] = mapped_column(String(24), index=True)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Результаты конвейера
    missing_items: Mapped[list | None] = mapped_column(JsonType)  # что не хватает (NEED_INFO)
    analyst_comment: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    score_grade: Mapped[str | None] = mapped_column(String(2))
    score_details: Mapped[dict | None] = mapped_column(JsonType)
    decision: Mapped[dict | None] = mapped_column(JsonType)  # оффер / контрпредложение / причины
    agreement: Mapped[dict | None] = mapped_column(JsonType)  # договор и график после подписания

    # Служебные поля конвейера
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enrichment_attempts: Mapped[int] = mapped_column(Integer, default=0)
    pipeline_error_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    assigned_analyst_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))

    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Оптимистическая блокировка: параллельные изменения одной заявки → 409
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    company: Mapped[Company] = relationship()
    applicant: Mapped[User] = relationship(foreign_keys=[applicant_id])
    product: Mapped[Product] = relationship()
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", order_by="ApplicationEvent.id"
    )
    checks: Mapped[list["ExternalCheck"]] = relationship(
        back_populates="application", order_by="ExternalCheck.id"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="application", order_by="Document.id"
    )


class ApplicationEvent(Base):
    """Аудит-лог: каждый переход статуса и значимое действие над заявкой."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))  # STATUS_CHANGED | DOCUMENT_UPLOADED | ...
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str | None] = mapped_column(String(24))
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="events")


class ExternalCheck(Base):
    """Результат обращения к внешнему источнику (ЕГРЮЛ, ФНС, БКИ)."""

    __tablename__ = "external_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    source: Mapped[str] = mapped_column(String(16))  # EGRUL | FNS | BKI
    status: Mapped[str] = mapped_column(String(16))  # OK | NOT_FOUND | ERROR
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    response: Mapped[dict | None] = mapped_column(JsonType)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="checks")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # STATEMENT | EQUIPMENT_INVOICE | OTHER
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    parsed: Mapped[dict | None] = mapped_column(JsonType)  # результат распознавания
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="documents")


class Notification(Base):
    """Уведомления внутри продукта (email/SMS не используются по условиям кейса)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
