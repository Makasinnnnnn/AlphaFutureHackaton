"""Pagination must reach older applications, keep stable order and enforce role access."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.conftest import login


def test_queue_pages_reach_beyond_legacy_cap_and_count_filtered_rows(api):
    from app.db import SessionLocal
    from app.models import Application, User

    prefix = f"VP{uuid4().hex[:8]}"
    at = datetime(2026, 10, 25, tzinfo=timezone.utc)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == 'anna@demo.ru'))
        for i in range(206):
            db.add(Application(number=f'{prefix}-{i:03}', applicant_id=user.id,
                               company_inn=user.company_inn, product_code='WORKING_CAPITAL',
                               amount=100_000, term_months=12, status='MANUAL_REVIEW' if i < 205 else 'DRAFT',
                               status_changed_at=at))
        db.commit()
    headers = login(api, 'analyst@demo.ru')
    params = {'q': prefix, 'status': 'MANUAL_REVIEW', 'limit': 100}
    pages = []
    for offset in (0, 100, 200):
        response = api.get('/api/analyst/applications/page', headers=headers, params=params | {'offset': offset})
        assert response.status_code == 200, response.text
        page = response.json()
        assert page['total'] == 205 and page['offset'] == offset and page['limit'] == 100
        pages.append(page['items'])
    assert [len(p) for p in pages] == [100, 100, 5]
    ids = [a['id'] for page in pages for a in page]
    assert len(set(ids)) == 205
    assert ids == sorted(ids, reverse=True)  # Equal timestamps use ID as a stable tie-breaker.
    empty = api.get('/api/analyst/applications/page', headers=headers, params=params | {'offset': 300}).json()
    assert empty['items'] == [] and empty['total'] == 205
    stats = api.get('/api/analyst/stats', headers=headers).json()
    assert 'DRAFT' not in stats['by_status']
    assert stats['total'] == sum(stats['by_status'].values())
    legacy = api.get('/api/analyst/applications', headers=headers, params={'q': prefix}).json()
    assert isinstance(legacy, list) and len(legacy) == 200


@pytest.mark.parametrize('params', [{'limit': 0}, {'limit': 101}, {'offset': -1}])
def test_queue_page_rejects_invalid_bounds(api, params):
    response = api.get('/api/analyst/applications/page', headers=login(api, 'analyst@demo.ru'), params=params)
    assert response.status_code == 422


def test_queue_page_is_analyst_only(api):
    assert api.get('/api/analyst/applications/page').status_code == 401
    assert api.get('/api/analyst/applications/page', headers=login(api, 'anna@demo.ru')).status_code == 403
