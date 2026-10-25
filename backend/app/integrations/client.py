"""HTTP-клиент внешних интеграций с таймаутами и ретраями.

В проверяемой версии все внешние источники (ЕГРЮЛ/ЕГРИП, «Прозрачный бизнес» ФНС, БКИ)
— локальные моки (сервис `mocks`). Контракты упрощены, но сохраняют смысл интеграции:
по ИНН получаем статус компании, сведения ФНС и кредитный отчёт.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.domain.scoring import STOP_REGISTRY_STATUSES

log = logging.getLogger("integrations")


def validate_payload(source: str, data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError('Источник вернул некорректную структуру данных')
    numeric = {'FNS': ('tax_arrears',), 'BKI': ('current_overdue_days', 'max_overdue_days_12m', 'total_monthly_payments')}
    booleans = {'FNS': ('mass_address', 'disqualified_director'), 'BKI': ('has_history',)}
    for field in numeric.get(source, ()):
        value = data.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1e15 or not math.isfinite(value):
            raise ValueError(f'Некорректное числовое поле источника: {field}')
        if field.endswith('_days') and int(value) != value:
            raise ValueError(f'Некорректное число дней: {field}')
    for field in booleans.get(source, ()):
        if not isinstance(data.get(field), bool):
            raise ValueError(f'Отсутствует или некорректен признак источника: {field}')
    if source == 'EGRUL' and data.get('status') not in {'ACTIVE'} | STOP_REGISTRY_STATUSES:
        raise ValueError('Источник не вернул известный статус компании')
    return data


@dataclass
class CallResult:
    source: str
    status: str  # OK | NOT_FOUND | ERROR
    data: dict | None
    error: str | None
    duration_ms: int
    attempts: int


class IntegrationClient:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        s = get_settings()
        self.base_url = (base_url or s.mocks_base_url).rstrip("/")
        self.timeout = s.integration_timeout_sec
        self.retries = s.integration_retries
        self.backoff = s.integration_backoff_sec
        self._transport = transport

    def _get(self, source: str, path: str) -> CallResult:
        started = time.monotonic()
        last_err = None
        attempts = 0
        with httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=self._transport) as client:
            for attempt in range(1, self.retries + 1):
                attempts = attempt
                try:
                    r = client.get(path)
                    if r.status_code == 200:
                        data = validate_payload(source, r.json())
                        return CallResult(source, "OK", data, None, int((time.monotonic() - started) * 1000), attempt)
                    if r.status_code == 404:
                        return CallResult(source, "NOT_FOUND", None, "Не найдено в источнике",
                                          int((time.monotonic() - started) * 1000), attempt)
                    last_err = f"HTTP {r.status_code}"
                except (httpx.HTTPError, ValueError, TypeError) as e:
                    last_err = f"{type(e).__name__}: {e}"
                log.warning("integration call failed", extra={"ctx": {"source": source, "attempt": attempt, "error": last_err}})
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** (attempt - 1)))
        return CallResult(source, "ERROR", None, last_err, int((time.monotonic() - started) * 1000), attempts)

    def egrul(self, inn: str) -> CallResult:
        return self._get("EGRUL", f"/egrul/{inn}")

    def fns(self, inn: str) -> CallResult:
        return self._get("FNS", f"/fns/transparent-business/{inn}")

    def bki(self, inn: str) -> CallResult:
        return self._get("BKI", f"/bki/report/{inn}")
