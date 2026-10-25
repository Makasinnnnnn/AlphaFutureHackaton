"""Independent invariants found in the second audit, beyond the happy paths."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.domain.finance import payment_schedule
from app.integrations.client import CallResult, IntegrationClient
from tests.conftest import login


@pytest.mark.parametrize('principal,rate,months', [
    (1000000.99, 19, 12), (100000, 19, 24), (500000.11, 19, 12),
    (30000000.99, 99.99, 60), (100000.01, 0, 120), (100000.01, 1e-14, 120),
])
def test_schedule_conserves_every_kopeck(principal, rate, months):
    rows = payment_schedule(principal, rate, months, date(2026, 1, 31))
    money = lambda value: Decimal(str(value))
    balance = money(principal)
    for row in rows:
        assert money(row['payment']) == money(row['principal']) + money(row['interest'])
        balance -= money(row['principal'])
        assert money(row['balance']) == balance
        assert row['principal'] >= 0 and row['balance'] >= 0
    assert sum(money(row['principal']) for row in rows) == money(principal)
    assert rows[-1]['balance'] == 0
    assert len({row['date'] for row in rows}) == months


def test_disabled_account_cannot_obtain_a_new_token(api):
    from app.db import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == 'anna@demo.ru'))
        user.is_active = False
        db.commit()
    try:
        response = api.post('/api/auth/login', json={'email': 'anna@demo.ru', 'password': 'demo2026'})
        assert response.status_code == 401
        assert 'access_token' not in response.json()
        assert all(account['email'] != 'anna@demo.ru' for account in api.get('/api/auth/demo-accounts').json())
    finally:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == 'anna@demo.ru'))
            user.is_active = True
            db.commit()


@pytest.mark.parametrize('source', ['BKI', 'FNS'])
def test_missing_risk_source_is_not_clean_credit_history(api, mocks_transport, source):
    from app.worker import run_once
    headers = login(api, 'anna@demo.ru')
    app = api.post('/api/applications', headers=headers, json={
        'product_code': 'WORKING_CAPITAL', 'amount': 500000, 'term_months': 12}).json()
    api.post(f"/api/applications/{app['id']}/submit", headers=headers, json={'consent': True})
    client = IntegrationClient(base_url='http://mocks', transport=mocks_transport)
    setattr(client, source.lower(), lambda inn: CallResult(source, 'NOT_FOUND', None, 'Not found', 1, 1))
    for _ in range(20):
        if run_once(batch=20, client=client) == 0:
            break
    result = api.get(f"/api/applications/{app['id']}", headers=headers).json()
    assert result['status']['code'] == 'MANUAL_REVIEW'
    assert result['decision']['offer'] is None


@pytest.mark.parametrize('field', ['amount', 'equipment_cost'])
def test_application_rejects_subkopeck_values(api, field):
    headers = login(api, 'anna@demo.ru')
    body = {'product_code': 'EQUIPMENT', 'amount': 500000, 'term_months': 12}
    if field == 'amount':
        body['amount'] = 500000.999
    else:
        body['collateral'] = {'equipment_name': 'Станок', 'equipment_cost': 600000.999}
    response = api.post('/api/applications', headers=headers, json=body)
    assert response.status_code == 422


def test_bank_financials_use_only_the_latest_contiguous_period(api):
    from app.db import SessionLocal
    from app.models import AccountTurnover, Company
    from app.services.companies import bank_financials
    with SessionLocal() as db:
        inn = '999000001234'
        db.add(Company(inn=inn, name='Тест разрыва истории', legal_form='IP', is_bank_client=True))
        db.flush()
        for month in ['2026-01', '2026-02', '2026-03', '2026-07', '2026-08', '2026-09']:
            db.add(AccountTurnover(company_inn=inn, month=month,
                                   inflow=100 if month >= '2026-07' else 1000000, outflow=0))
        db.flush()
        financials = bank_financials(db, inn)
        assert financials['months_count'] == 3
        assert financials['avg_monthly_inflow'] == 100
        assert financials['period_from'] == '2026-07'
        db.rollback()


@pytest.mark.parametrize('source', ['EGRUL', 'FNS', 'BKI'])
def test_integration_rejects_a_report_for_another_company(source):
    import httpx
    payloads = {
        'EGRUL': {'status': 'ACTIVE'},
        'FNS': {'mass_address': False, 'disqualified_director': False, 'tax_arrears': 0},
        'BKI': {'has_history': True, 'current_overdue_days': 0,
                'max_overdue_days_12m': 0, 'total_monthly_payments': 0},
    }
    payload = payloads[source] | {'inn': '0000000000'}
    client = IntegrationClient(base_url='http://mocks', transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)))
    client.retries = 1
    assert getattr(client, source.lower())('701712345678').status == 'ERROR'


@pytest.mark.parametrize('patch', [
    {'registered_at': 'not-a-date'}, {'registered_at': '2099-01-01'},
    {'name': {'unexpected': 'object'}}, {'legal_form': 'X' * 100},
])
def test_registry_malformed_fields_are_not_successful_checks(patch):
    import httpx
    payload = {'status': 'ACTIVE', 'inn': '701712345678'} | patch
    client = IntegrationClient(base_url='http://mocks', transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)))
    client.retries = 1
    assert client.egrul('701712345678').status == 'ERROR'


def test_stale_statement_cannot_enable_resubmit_but_fresh_one_can(api, run_pipeline):
    from app.domain.finance import add_months
    headers = login(api, 'kovalev@demo.ru')
    app = api.post('/api/applications', headers=headers, json={
        'product_code': 'WORKING_CAPITAL', 'amount': 500000, 'term_months': 12}).json()
    api.post(f"/api/applications/{app['id']}/submit", headers=headers, json={'consent': True})
    run_pipeline()
    path = f"/api/applications/{app['id']}"
    stale = b'date,amount\n2024-01-01,1000000\n2024-02-01,1000000\n2024-03-01,1000000'
    response = api.post(path + '/documents', headers=headers, data={'kind': 'STATEMENT'},
                        files={'file': ('old.csv', stale, 'text/csv')})
    assert response.status_code == 201
    assert response.json()['financials']['months_count'] == 3
    assert 'RESUBMIT' not in response.json()['allowed_actions']
    assert api.post(path + '/resubmit', headers=headers).status_code == 409
    months = [add_months(date.today().replace(day=1), -i).isoformat() for i in (3, 2, 1)]
    fresh = ('date,amount\n' + '\n'.join(f'{month},1000000' for month in months)).encode()
    response = api.post(path + '/documents', headers=headers, data={'kind': 'STATEMENT'},
                        files={'file': ('fresh.csv', fresh, 'text/csv')})
    assert response.status_code == 201
    assert 'RESUBMIT' in response.json()['allowed_actions']
    assert api.post(path + '/resubmit', headers=headers).status_code == 200


@pytest.mark.parametrize('identifier', [0, -1, 2**31, 10**30])
@pytest.mark.parametrize('method,path,email', [
    ('get', '/api/applications/{id}', 'anna@demo.ru'),
    ('get', '/api/analyst/applications/{id}', 'analyst@demo.ru'),
    ('get', '/api/analyst/applications/1/documents/{id}', 'analyst@demo.ru'),
    ('post', '/api/notifications/{id}/read', 'anna@demo.ru'),
    ('delete', '/api/notifications/{id}', 'anna@demo.ru'),
])
def test_invalid_identifiers_are_rejected_before_database_access(api, identifier, method, path, email):
    headers = login(api, email)
    assert getattr(api, method)(path.format(id=identifier), headers=headers).status_code == 422


@pytest.mark.parametrize('identifier', [2**31, 2**40])
def test_oversized_token_subject_is_unauthorized(api, identifier):
    import jwt
    from datetime import UTC, datetime, timedelta
    from app.config import get_settings
    current = datetime.now(UTC)
    token = jwt.encode({'sub': str(identifier), 'iat': current, 'exp': current + timedelta(minutes=1)},
                       get_settings().jwt_secret, algorithm='HS256')
    assert api.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401
