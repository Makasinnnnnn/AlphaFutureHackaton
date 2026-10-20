"""Единая точка смены статуса заявки: валидация перехода + аудит + уведомления."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.statuses import CLIENT_COPY, PIPELINE, Actor, Status, assert_transition
from app.models import Application, ApplicationEvent, Notification, User

log = logging.getLogger("workflow")

CLIENT_NOTIFY = {
    Status.NEED_INFO: "Нужна дополнительная информация",
    Status.MANUAL_REVIEW: "Заявку рассматривает специалист",
    Status.APPROVED: "Кредит одобрен",
    Status.COUNTER_OFFER: "Банк предлагает другие условия",
    Status.REJECTED: "Решение по заявке",
    Status.ISSUED: "Кредит выдан",
}


def now() -> datetime:
    return datetime.now(UTC)


def add_event(
    db: Session,
    app: Application,
    event_type: str,
    actor: Actor,
    actor_id: int | None = None,
    reason: str | None = None,
    payload: dict | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
) -> ApplicationEvent:
    ev = ApplicationEvent(
        application_id=app.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_type=actor.value,
        actor_id=actor_id,
        reason=reason,
        payload=payload,
    )
    db.add(ev)
    return ev


def notify(db: Session, user_id: int, app: Application | None, title: str, body: str) -> None:
    db.add(Notification(user_id=user_id, application_id=app.id if app else None, title=title, body=body))


def transition(
    db: Session,
    app: Application,
    to: Status,
    actor: Actor,
    actor_id: int | None = None,
    reason: str | None = None,
    payload: dict | None = None,
) -> None:
    src = Status(app.status)
    assert_transition(src, to, actor)
    app.status = to.value
    app.status_changed_at = now()
    app.next_action_at = (
        now() + timedelta(seconds=get_settings().pipeline_step_delay_sec) if to in PIPELINE else None
    )
    add_event(db, app, "STATUS_CHANGED", actor, actor_id, reason, payload, src.value, to.value)
    log.info(
        "status changed",
        extra={"ctx": {"application": app.number, "from": src.value, "to": to.value, "actor": actor.value}},
    )

    if to in CLIENT_NOTIFY:
        body = CLIENT_COPY[to]["what"] + " " + CLIENT_COPY[to]["next"]
        notify(db, app.applicant_id, app, f"{CLIENT_NOTIFY[to]} · {app.number}", body)
    if to == Status.MANUAL_REVIEW:
        for (analyst_id,) in db.execute(select(User.id).where(User.role == "ANALYST", User.is_active)):
            notify(db, analyst_id, app, f"Новая заявка на ручное рассмотрение · {app.number}",
                   reason or "Требуется решение аналитика.")
