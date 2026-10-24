"""Воркер кредитного конвейера.

Забирает заявки, готовые к следующему автоматическому этапу, через
SELECT ... FOR UPDATE SKIP LOCKED — можно запускать несколько реплик воркера
без двойной обработки (горизонтальное масштабирование). Ошибка в одной заявке
не останавливает обработку остальных.
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import SessionLocal
from app.domain.statuses import PIPELINE, Actor, Status
from app.integrations.client import IntegrationClient
from app.logging_conf import setup_logging
from app.models import Application
from app.services.pipeline import process_step
from app.services.workflow import add_event, now, transition

log = logging.getLogger("worker")
_running = True


def _stop(*_):
    global _running
    _running = False


def run_once(batch: int = 10, client: IntegrationClient | None = None) -> int:
    """Обрабатывает до `batch` заявок, каждую в отдельной транзакции. Возвращает число обработанных."""
    processed = 0
    client = client or IntegrationClient()
    for _ in range(batch):
        with SessionLocal() as db:
            app = db.scalars(
                select(Application)
                .where(Application.status.in_([s.value for s in PIPELINE]),
                       (Application.next_action_at.is_(None)) | (Application.next_action_at <= now()))
                .order_by(Application.next_action_at.nulls_first(), Application.id)
                .limit(1)
                .with_for_update(skip_locked=True, of=Application)
                .options(selectinload(Application.checks), selectinload(Application.documents),
                         selectinload(Application.company), selectinload(Application.product))
            ).first()
            if app is None:
                break
            app_id, failed_version, failed_status = app.id, app.version, app.status
            try:
                process_step(db, app, client)
                app.pipeline_error_attempts = 0
                db.commit()
                processed += 1
            except Exception as exc:
                db.rollback()
                log.exception("pipeline step failed", extra={"ctx": {"application_id": app_id}})
                with SessionLocal() as db2:
                    a = db2.scalars(select(Application).where(Application.id == app_id).with_for_update()).first()
                    # Another worker/client may have changed the row after rollback.
                    if a and a.version == failed_version and a.status == failed_status:
                        s = get_settings()
                        a.pipeline_error_attempts += 1
                        add_event(db2, a, "PIPELINE_ERROR", Actor.SYSTEM,
                                  reason="Техническая ошибка обработки",
                                  payload={"attempt": a.pipeline_error_attempts, "stage": failed_status,
                                           "error_type": type(exc).__name__})
                        if a.pipeline_error_attempts >= s.pipeline_max_error_attempts:
                            a.decision = (a.decision or {}) | {"outcome": "MANUAL_REVIEW",
                                "recommendation": "Автоматическая обработка остановлена после повторных технических ошибок. Проверьте данные и журнал обработки."}
                            transition(db2, a, Status.MANUAL_REVIEW, Actor.SYSTEM,
                                       reason="Повторная техническая ошибка — заявка передана специалисту")
                        else:
                            a.next_action_at = now() + timedelta(seconds=s.pipeline_error_retry_delay_sec)
                        db2.commit()
    return processed


def main() -> None:
    s = get_settings()
    setup_logging(s.log_level)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker started", extra={"ctx": {"poll_sec": s.pipeline_poll_interval_sec}})
    client = IntegrationClient()
    while _running:
        try:
            n = run_once(client=client)
        except Exception:
            log.exception("worker loop error")
            n = 0
        if n == 0:
            time.sleep(s.pipeline_poll_interval_sec)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
