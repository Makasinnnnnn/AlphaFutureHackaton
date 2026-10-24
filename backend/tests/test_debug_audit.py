"""Regression checks from the full 24 October debug pass."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from time import sleep

import pytest

from tests.conftest import login


def draft(api, headers):
    response = api.post('/api/applications', headers=headers, json={
        'product_code': 'WORKING_CAPITAL', 'purpose': 'PURCHASE_GOODS',
        'amount': 1_000_000, 'term_months': 12,
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize('field', ['amount', 'term_months', 'product_code'])
def test_patch_null_required_field_is_validation_error(api, field):
    headers = login(api, 'anna@demo.ru')
    app = draft(api, headers)
    response = api.patch(f"/api/applications/{app['id']}", headers=headers,
                         json={field: None, 'version': app['version']})
    assert response.status_code == 422, response.text
    saved = api.get(f"/api/applications/{app['id']}", headers=headers).json()
    if field == 'product_code':
        assert saved['product']['code'] == app['product']['code']
    else:
        assert saved[field] == app[field]


def test_patch_rejects_unknown_purpose(api):
    headers = login(api, 'anna@demo.ru')
    app = draft(api, headers)
    response = api.patch(f"/api/applications/{app['id']}", headers=headers,
                         json={'purpose': 'NOT_A_PURPOSE', 'version': app['version']})
    assert response.status_code == 422


def test_delete_notification_cors_preflight(api):
    response = api.options('/api/notifications/1', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'DELETE',
        'Access-Control-Request-Headers': 'authorization',
    })
    assert response.status_code == 200, response.text
    assert 'DELETE' in response.headers['access-control-allow-methods']


def test_signature_cannot_be_whitespace(api, run_pipeline):
    headers = login(api, 'anna@demo.ru')
    app = draft(api, headers)
    assert api.post(f"/api/applications/{app['id']}/submit", headers=headers, json={'consent': True}).status_code == 200
    run_pipeline()
    assert api.post(f"/api/applications/{app['id']}/accept", headers=headers).status_code == 200
    response = api.post(f"/api/applications/{app['id']}/sign", headers=headers,
                        json={'confirm': True, 'signer_name': '   '})
    assert response.status_code == 422


def test_concurrent_idempotency_key_creates_one_application(api, monkeypatch):
    from app.services import applications
    original = applications._check_params
    def slow_validation(*args):
        sleep(0.1)  # Widen the real read-before-insert race; no fake database.
        return original(*args)
    monkeypatch.setattr(applications, '_check_params', slow_validation)
    headers = login(api, 'anna@demo.ru') | {'Idempotency-Key': str(uuid4())}
    payload = {'product_code': 'WORKING_CAPITAL', 'amount': 1_000_000, 'term_months': 12}
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: api.post('/api/applications', headers=headers, json=payload), range(4)))
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()['id'] for r in responses}) == 1


@pytest.mark.parametrize('rate', [0.0, 1e-15, 0.01, 19.0, 99.0])
def test_annuity_remains_stable_at_very_small_rates(rate):
    from app.domain.finance import annuity_payment, annuity_principal, payment_schedule
    from datetime import date
    principal = 1_000_000
    payment = annuity_payment(principal, rate, 12)
    assert payment >= principal / 12 - 0.0001
    assert annuity_principal(payment, rate, 12) == pytest.approx(principal, rel=1e-10)
    schedule = payment_schedule(principal, rate, 12, date(2026, 1, 31))
    assert schedule[-1]['balance'] == 0
    assert sum(row['principal'] for row in schedule) == pytest.approx(principal, abs=0.12)


def test_overlong_csv_field_returns_parse_error():
    from app.domain.statement_parser import parse_statement, StatementParseError
    with pytest.raises(StatementParseError):
        parse_statement(('Дата;Сумма\n2026-01-01;' + '1' * 150_000).encode())


def test_analyst_cannot_submit_whitespace_reason(api):
    headers = login(api, 'analyst@demo.ru')
    response = api.post('/api/analyst/applications/999999/decision', headers=headers,
                        json={'action': 'REJECT', 'version': 1, 'comment': '   '})
    assert response.status_code == 422


@pytest.mark.parametrize('subject', [None, 'not-an-id', '0', '-1', '99999999999999999999999999999999'])
def test_invalid_signed_token_returns_401_instead_of_500(api, subject):
    import jwt
    from datetime import UTC, datetime, timedelta
    from app.config import get_settings
    claims = {'iat': datetime.now(UTC), 'exp': datetime.now(UTC) + timedelta(minutes=1)}
    if subject is not None:
        claims['sub'] = subject
    token = jwt.encode(claims, get_settings().jwt_secret, algorithm='HS256')
    assert api.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401
