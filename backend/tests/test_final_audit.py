from datetime import date

import pytest

from app.domain.decision import decide
from app.domain.finance import annuity_payment
from app.domain.statement_history import contiguous_tail, history_problem
from tests.test_domain import WC, good_profile, inp
from tests.conftest import login


def test_automatic_offer_preserves_kopecks_and_payment_principal():
    decision = decide(WC, good_profile_score(), inp(amount=1_000_000.99))
    assert decision.outcome == 'APPROVED'
    assert decision.offer.amount == 1_000_000.99
    assert decision.offer.monthly_payment == pytest.approx(annuity_payment(1_000_000.99, decision.offer.rate, 12))


def good_profile_score():
    from app.domain.scoring import score
    return score(good_profile())


def manual_application(api, run_pipeline, amount=1_000_000):
    client = login(api, 'sever@demo.ru')
    response = api.post('/api/applications', headers=client, json={
        'product_code': 'WORKING_CAPITAL', 'amount': amount, 'term_months': 12, 'purpose': 'PURCHASE_GOODS'})
    app = response.json()
    assert api.post(f"/api/applications/{app['id']}/submit", headers=client, json={'consent': True}).status_code == 200
    run_pipeline()
    analyst = login(api, 'analyst@demo.ru')
    app = api.get(f"/api/analyst/applications/{app['id']}", headers=analyst).json()
    assert app['status']['code'] == 'MANUAL_REVIEW'
    return app, analyst


def test_analyst_changed_terms_become_counteroffer_and_keep_comparison(api, run_pipeline):
    app, analyst = manual_application(api, run_pipeline)
    response = api.post(f"/api/analyst/applications/{app['id']}/decision", headers=analyst, json={
        'action': 'APPROVE', 'version': app['version'], 'amount': 999_999.99, 'term_months': 15,
        'rate': 19, 'comment': 'Подтверждены изменённые условия'})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['status']['code'] == 'COUNTER_OFFER'
    decision = result['decision']
    assert decision['offer']['amount'] == 999_999.99
    assert decision['offer']['monthly_payment'] == round(annuity_payment(999_999.99, 19, 15), 2)
    assert decision['requested_terms']['monthly_payment'] > 0
    assert decision['offer_limits']['dti'] != decision['limits']['dti']


def test_analyst_unchanged_terms_stay_approved_with_kopecks(api, run_pipeline):
    app, analyst = manual_application(api, run_pipeline, 1_000_000.99)
    response = api.post(f"/api/analyst/applications/{app['id']}/decision", headers=analyst, json={
        'action': 'APPROVE', 'version': app['version'], 'comment': 'Условия подтверждены'})
    assert response.status_code == 200, response.text
    assert response.json()['status']['code'] == 'APPROVED'
    assert response.json()['decision']['offer']['amount'] == 1_000_000.99


@pytest.mark.parametrize('months,expected', [
    (['2026-07', '2026-08', '2026-09'], None),
    (['2026-06', '2026-07', '2026-08'], None),
    (['2024-01', '2025-02', '2026-09'], 'последовательных'),
    (['2026-01', '2026-02', '2026-03'], 'устарела'),
    (['2026-09', '2026-10', '2026-11'], 'будущие'),
    (['2026-13'], 'корректными'),
])
def test_statement_history_policy(months, expected):
    rows = [{'month': month, 'inflow': 0, 'outflow': 0} for month in months]
    problem = history_problem(rows, date(2026, 10, 25))
    assert problem is None if expected is None else expected in problem


def test_history_continuity_crosses_year_and_keeps_explicit_zero_months():
    rows = [{'month': month, 'inflow': 0} for month in ['2025-09', '2025-11', '2025-12', '2026-01']]
    assert len(contiguous_tail(rows)) == 3
    assert history_problem(rows, date(2026, 2, 1)) is None


def test_sparse_statement_does_not_bypass_validation(api, run_pipeline):
    headers = login(api, 'kovalev@demo.ru')
    app = api.post('/api/applications', headers=headers, json={
        'product_code': 'WORKING_CAPITAL', 'amount': 500_000, 'term_months': 12}).json()
    response = api.post(f"/api/applications/{app['id']}/documents", headers=headers,
        data={'kind': 'STATEMENT'}, files={'file': ('sparse.csv', b'date,amount\n2024-01-01,1000000\n2025-01-01,1000000\n2026-09-01,1000000', 'text/csv')})
    assert response.status_code == 201, response.text
    assert response.json()['financials']['months_count'] == 1
    assert api.post(f"/api/applications/{app['id']}/submit", headers=headers, json={'consent': True}).status_code == 200
    run_pipeline()
    result = api.get(f"/api/applications/{app['id']}", headers=headers).json()
    assert result['status']['code'] == 'NEED_INFO'
    assert any(i['code'] == 'STATEMENT' for i in result['missing_items'])


@pytest.mark.parametrize('body', [
    b'{"has_history":true,"current_overdue_days":0,"max_overdue_days_12m":0,"total_monthly_payments":NaN}',
    b'{"has_history":true,"current_overdue_days":0,"max_overdue_days_12m":0,"total_monthly_payments":"NaN"}',
    b'{"has_history":true,"current_overdue_days":0.5,"max_overdue_days_12m":0,"total_monthly_payments":0}',
    b'{}', b'null', b'not json',
    b'{"has_history":true,"current_overdue_days":0,"max_overdue_days_12m":0,"total_monthly_payments":' + b'9' * 400 + b'}',
])
def test_malformed_source_is_retried_then_reported_as_error(body):
    import httpx
    from app.integrations.client import IntegrationClient
    client = IntegrationClient(base_url='http://mocks', transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)))
    client.retries, client.backoff = 2, 0
    result = client.bki('701712345678')
    assert result.status == 'ERROR' and result.data is None and result.attempts == 2


def test_collateral_name_is_trimmed_before_completeness_check():
    from app.schemas import CollateralIn
    assert CollateralIn(equipment_name='   ', equipment_cost=100000).equipment_name == ''


def test_unknown_registry_state_is_not_treated_as_clean_company():
    from app.integrations.client import validate_payload
    with pytest.raises(ValueError):
        validate_payload('EGRUL', {'status': 'UNKNOWN_NEW_STATE'})
