"""Данные о компании клиента: реестр (мок ЕГРЮЛ/ЕГРИП) и внутренние обороты банка."""
from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.finance import summarize_turnovers
from app.integrations.client import IntegrationClient
from app.models import AccountTurnover, Company

SOURCE_LABELS = {
    "BANK_ACCOUNT": "Обороты по вашему счёту в банке — вводить ничего не нужно",
    "STATEMENT_UPLOAD": "Распознано из загруженной выписки",
}


def months_between(start: date | None, end: date | None = None) -> int | None:
    if start is None:
        return None
    end = end or datetime.now(UTC).date()
    return (end.year - start.year) * 12 + (end.month - start.month) - (1 if end.day < start.day else 0)


def apply_registry_data(company: Company, data: dict) -> None:
    company.name = data.get("name") or company.name
    company.legal_form = data.get("legal_form") or company.legal_form
    company.ogrn = data.get("ogrn")
    company.okved = data.get("okved")
    company.okved_name = data.get("okved_name")
    company.address = data.get("address")
    company.director = data.get("director")
    if data.get("registered_at"):
        company.registered_at = date.fromisoformat(data["registered_at"])
    company.registry_status = data.get("status")
    company.registry_synced_at = datetime.now(UTC)


def sync_company(db: Session, company: Company, client: IntegrationClient | None = None) -> bool:
    """Обновляет реквизиты компании из реестра. Возвращает False, если реестр недоступен
    (тогда используем последние сохранённые данные — сценарий не ломается)."""
    res = (client or IntegrationClient()).egrul(company.inn)
    if res.status == "OK" and res.data:
        apply_registry_data(company, res.data)
        return True
    return False


def bank_financials(db: Session, inn: str, months: int = 6) -> dict | None:
    rows = db.scalars(
        select(AccountTurnover).where(AccountTurnover.company_inn == inn).order_by(AccountTurnover.month.desc()).limit(months)
    ).all()
    if not rows:
        return None
    month_rows = [{"month": r.month, "inflow": float(r.inflow), "outflow": float(r.outflow)} for r in reversed(rows)]
    return build_financials("BANK_ACCOUNT", month_rows)


def build_financials(source: str, month_rows: list[dict]) -> dict:
    return {
        "source": source,
        "source_label": SOURCE_LABELS.get(source),
        "months": month_rows,
        **summarize_turnovers(month_rows),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def bank_history_months(db: Session, inn: str) -> int:
    return len(db.scalars(select(AccountTurnover.id).where(AccountTurnover.company_inn == inn)).all())
