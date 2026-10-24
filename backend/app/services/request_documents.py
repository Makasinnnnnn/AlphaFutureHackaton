"""Resolve document snapshots, including requests created before snapshot support."""
from app.models import Application


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
