from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.decision import ProductTerms
from app.models import Product
from app.schemas import ProductOut


def list_products(db: Session) -> list[Product]:
    return list(db.scalars(select(Product).where(Product.is_active).order_by(Product.sort_order)).all())


def to_terms(p: Product) -> ProductTerms:
    return ProductTerms(
        code=p.code,
        name=p.name,
        min_amount=float(p.min_amount),
        max_amount=float(p.max_amount),
        min_term=p.min_term_months,
        max_term=p.max_term_months,
        base_rate=float(p.base_rate),
        rules=p.rules,
        is_overdraft=bool(p.rules.get("is_overdraft")),
    )


def to_out(p: Product) -> ProductOut:
    return ProductOut(
        code=p.code,
        name=p.name,
        short_description=p.short_description,
        purposes=p.purposes,
        min_amount=float(p.min_amount),
        max_amount=float(p.max_amount),
        min_term_months=p.min_term_months,
        max_term_months=p.max_term_months,
        base_rate=float(p.base_rate),
        requires_collateral=p.requires_collateral,
        min_business_age_months=p.rules.get("min_business_age_months", 0),
    )
