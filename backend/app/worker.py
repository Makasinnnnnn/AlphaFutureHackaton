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
from app.domain.statuses import PIPELINE
from app.integrations.client import IntegrationClient
from app.logging_conf import setup_logging
from app.models import Application
from app.services.pipeline import process_step
from app.services.workflow import now

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
            try:
                process_step(db, app, client)
                db.commit()
                processed += 1
            except Exception:
                db.rollback()
                log.exception("pipeline step failed", extra={"ctx": {"application_id": app.id}})
                # откладываем проблемную заявку, чтобы не крутиться на ней
                with SessionLocal() as db2:
                    a = db2.get(Application, app.id)
                    if a:
                        a.next_action_at = now() + timedelta(seconds=10)
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
