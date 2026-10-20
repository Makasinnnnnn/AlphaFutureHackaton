"""Загрузка справочников и синтетических данных. Идемпотентно — можно запускать повторно."""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AccountTurnover, Company, Product, User
from app.security import hash_password

log = logging.getLogger("seed")

DEMO_PASSWORD = "demo2026"
DATA_PATH = Path(os.getenv("SYNTHETIC_DATA", Path(__file__).resolve().parents[2] / "data/synthetic/companies.json"))

PRODUCTS = [
    {
        "code": "WORKING_CAPITAL",
        "name": "Оборотный экспресс-кредит",
        "short_description": "Деньги на закупки, зарплату и текущие расходы. Без залога, решение за минуты.",
        "purposes": ["PURCHASE_GOODS", "CASH_GAP", "EXPANSION", "EQUIPMENT"],
        "min_amount": 100_000, "max_amount": 5_000_000, "min_term_months": 3, "max_term_months": 24,
        "base_rate": 19.0, "requires_collateral": False, "sort_order": 1,
        "rules": {"auto_approve_score": 60, "review_score": 45, "min_business_age_months": 6,
                  "max_revenue_share": 0.4, "max_dti": 0.5},
    },
    {
        "code": "EQUIPMENT",
        "name": "Кредит на оборудование",
        "short_description": "Покупка оборудования и транспорта. Залог — покупаемое оборудование, поэтому ставка ниже.",
        "purposes": ["EQUIPMENT", "EXPANSION"],
        "min_amount": 300_000, "max_amount": 30_000_000, "min_term_months": 12, "max_term_months": 60,
        "base_rate": 17.0, "requires_collateral": True, "sort_order": 2,
        "rules": {"auto_approve_score": 60, "review_score": 40, "min_business_age_months": 12,
                  "max_revenue_share": 0.8, "max_dti": 0.6, "max_ltv": 0.9},
    },
    {
        "code": "OVERDRAFT",
        "name": "Овердрафт",
        "short_description": "Резерв на счёте на случай кассового разрыва. Проценты только за использованные дни.",
        "purposes": ["CASH_GAP", "PURCHASE_GOODS"],
        "min_amount": 50_000, "max_amount": 10_000_000, "min_term_months": 12, "max_term_months": 12,
        "base_rate": 21.0, "requires_collateral": False, "sort_order": 3,
        "rules": {"auto_approve_score": 70, "review_score": 55, "min_business_age_months": 6,
                  "max_turnover_share": 0.3, "max_dti": 0.5, "is_overdraft": True},
    },
]

ANALYST = {"email": "analyst@demo.ru", "full_name": "Морозова Елена Игоревна", "position": "Кредитный аналитик МСБ"}


def seed(db: Session) -> None:
    for p in PRODUCTS:
        obj = db.get(Product, p["code"]) or Product(code=p["code"])
        for k, v in p.items():
            setattr(obj, k, v)
        db.merge(obj)

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    for c in data["companies"]:
        e = c["egrul"]
        comp = db.get(Company, e["inn"]) or Company(inn=e["inn"])
        comp.name, comp.legal_form, comp.ogrn = e["name"], e["legal_form"], e["ogrn"]
        comp.okved, comp.okved_name, comp.address, comp.director = e["okved"], e["okved_name"], e["address"], e["director"]
        comp.registered_at = date.fromisoformat(e["registered_at"])
        comp.registry_status = e["status"]
        comp.is_bank_client = c["bank"]["is_client"]
        db.merge(comp)
        db.flush()

        existing = {t.month: t for t in db.scalars(select(AccountTurnover).where(AccountTurnover.company_inn == e["inn"]))}
        for t in c["bank"]["turnovers"]:
            row = existing.get(t["month"]) or AccountTurnover(company_inn=e["inn"], month=t["month"])
            row.inflow, row.outflow = t["inflow"], t["outflow"]
            db.add(row)

        u = c["user"]
        if not db.scalars(select(User).where(User.email == u["email"])).first():
            db.add(User(email=u["email"], password_hash=hash_password(DEMO_PASSWORD), role="CLIENT",
                        full_name=u["full_name"], position=u["position"], company_inn=e["inn"]))

    if not db.scalars(select(User).where(User.email == ANALYST["email"])).first():
        db.add(User(email=ANALYST["email"], password_hash=hash_password(DEMO_PASSWORD), role="ANALYST",
                    full_name=ANALYST["full_name"], position=ANALYST["position"]))
    db.commit()
    log.info("seed completed")


def main() -> None:
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
