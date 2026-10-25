"""Resolve document snapshots, including requests created before snapshot support."""
from app.models import Application
from app.domain.statuses import Status
from app.domain.validation import missing_items


def request_items(app: Application) -> list[dict] | None:
    if app.missing_items is None:
        return None
    items = [dict(item) for item in app.missing_items]
    legacy = [item for item in items if item.get('code') == 'ANALYST_REQUEST'
              and item.get('document_ids_before_request') is None]
    if not legacy:
        return items
    events = [event for event in app.events if event.event_type == 'STATUS_CHANGED'
              and event.to_status == 'NEED_INFO' and event.actor_type == 'ANALYST']
    if not events:
        return items  # No trustworthy boundary: keep the request blocked.
    boundary = max(events, key=lambda event: event.id).created_at
    baseline = [document.id for document in app.documents if document.created_at <= boundary]
    for item in legacy:
        item['document_ids_before_request'] = baseline
    return items


def can_resubmit(app: Application) -> bool:
    """Use the same server-side prerequisites for the button and the action."""
    if app.status != Status.NEED_INFO:
        return False
    requests = [item for item in (request_items(app) or []) if item.get('code') == 'ANALYST_REQUEST']
    if requests:
        return all(item.get('document_ids_before_request') is not None and any(
            document.id not in item['document_ids_before_request'] for document in app.documents
        ) for item in requests)
    return not missing_items(product_code=app.product_code,
                             requires_collateral=app.product.requires_collateral,
                             financials=app.financials, collateral=app.collateral,
                             document_kinds={document.kind for document in app.documents})
