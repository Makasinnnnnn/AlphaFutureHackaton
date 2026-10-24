"""Сквозные сценарии через HTTP API + воркер конвейера (по одному на каждую персону)."""
from pathlib import Path

from tests.conftest import login

TEST_DATA = Path(__file__).resolve().parents[2] / "test-data"


def create_and_submit(api, h, **body):
    body.setdefault("purpose", "PURCHASE_GOODS")
    r = api.post("/api/applications", json=body, headers=h)
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    r = api.post(f"/api/applications/{app_id}/submit", json={"consent": True}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"]["code"] == "SUBMITTED"
    return app_id


def get(api, h, app_id):
    r = api.get(f"/api/applications/{app_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_health(api):
    assert api.get("/health/live").json() == {"status": "ok"}


def test_login_errors(api):
    assert api.post("/api/auth/login", json={"email": "anna@demo.ru", "password": "bad"}).status_code == 401
    assert api.get("/api/applications").status_code == 401


def test_company_prefilled_from_registry(api, mocks_transport, monkeypatch):
    h = login(api, "anna@demo.ru")
    c = api.get("/api/companies/me", headers=h).json()
    assert c["inn"] == "701712345678" and c["okved"] == "56.10" and c["business_age_months"] > 60
    fin = api.get("/api/companies/me/financials", headers=h).json()
    assert fin["source"] == "BANK_ACCOUNT" and fin["months_count"] == 6


def test_recommend_by_text(api):
    h = login(api, "anna@demo.ru")
    r = api.post("/api/assistant/recommend", json={"text": "нужно купить новый станок для цеха"}, headers=h).json()
    assert r["purpose"] == "EQUIPMENT" and r["recommendations"][0]["product"]["code"] == "EQUIPMENT"
    assert r["engine"] == "rules"


def test_happy_path_to_issued(api, run_pipeline):
    h = login(api, "anna@demo.ru")
    app_id = create_and_submit(api, h, product_code="WORKING_CAPITAL", amount=2_000_000, term_months=12)
    run_pipeline()
    a = get(api, h, app_id)
    assert a["status"]["code"] == "APPROVED"
    assert a["financials"]["source"] == "BANK_ACCOUNT"  # обороты подтянуты без ввода клиентом
    assert "rules_fired" not in a["decision"] and "score_details" not in a  # клиенту не раскрываем веса
    a = api.post(f"/api/applications/{app_id}/accept", headers=h).json()
    assert a["status"]["code"] == "SIGNING" and len(a["agreement"]["schedule"]) == 12
    a = api.post(f"/api/applications/{app_id}/sign", json={"confirm": True, "signer_name": "Смирнова А. С."},
                 headers=h).json()
    assert a["status"]["code"] == "ISSUED" and a["agreement"]["disbursement"]["status"] == "SIMULATED"
    done = [t["status"] for t in a["timeline"] if t["state"] != "upcoming"]
    assert done == ["DRAFT", "SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING", "APPROVED", "SIGNING", "ISSUED"]
    n = api.get("/api/notifications", headers=h).json()
    assert n["unread"] >= 2


def test_counter_offer(api, run_pipeline):
    h = login(api, "start@demo.ru")
    app_id = create_and_submit(api, h, product_code="WORKING_CAPITAL", amount=5_000_000, term_months=24)
    run_pipeline()
    a = get(api, h, app_id)
    assert a["status"]["code"] == "COUNTER_OFFER"
    assert a["decision"]["offer"]["amount"] == 3_120_000
    a = api.post(f"/api/applications/{app_id}/accept", headers=h).json()
    assert a["agreement"]["amount"] == 3_120_000


def test_need_info_then_statement_then_approved(api, run_pipeline):
    h = login(api, "kovalev@demo.ru")
    app_id = create_and_submit(api, h, product_code="EQUIPMENT", amount=1_800_000, term_months=36, purpose="EQUIPMENT")
    run_pipeline()
    a = get(api, h, app_id)
    assert a["status"]["code"] == "NEED_INFO"
    assert {i["code"] for i in a["missing_items"]} == {"STATEMENT", "EQUIPMENT_INFO", "EQUIPMENT_INVOICE"}

    # нельзя менять сумму на этапе дозапроса
    assert api.patch(f"/api/applications/{app_id}", json={"amount": 100_000}, headers=h).status_code == 409
    r = api.patch(f"/api/applications/{app_id}", headers=h, json={
        "collateral": {"equipment_name": "Фрезерный станок с ЧПУ", "equipment_cost": 2_000_000}})
    assert r.status_code == 200, r.text
    with open(TEST_DATA / "statement_kovalev_6m.csv", "rb") as f:
        r = api.post(f"/api/applications/{app_id}/documents", headers=h, data={"kind": "STATEMENT"},
                     files={"file": ("statement.csv", f, "text/csv")})
    assert r.status_code == 201, r.text
    assert r.json()["financials"]["source"] == "STATEMENT_UPLOAD"
    assert r.json()["financials"]["avg_monthly_inflow"] == 900_000
    with open(TEST_DATA / "invoice_cnc_machine.pdf", "rb") as f:
        api.post(f"/api/applications/{app_id}/documents", headers=h, data={"kind": "EQUIPMENT_INVOICE"},
                 files={"file": ("invoice.pdf", f, "application/pdf")})
    assert api.post(f"/api/applications/{app_id}/resubmit", headers=h).status_code == 200
    run_pipeline()
    a = get(api, h, app_id)
    assert a["status"]["code"] == "APPROVED" and a["decision"]["offer"]["rate"] == 17.0


def test_bad_statement_is_rejected_with_message(api):
    h = login(api, "kovalev@demo.ru")
    r = api.post("/api/applications", headers=h, json={"product_code": "WORKING_CAPITAL", "amount": 500_000,
                                                        "term_months": 6})
    app_id = r.json()["id"]
    r = api.post(f"/api/applications/{app_id}/documents", headers=h, data={"kind": "STATEMENT"},
                 files={"file": ("x.csv", b"foo;bar\n1;2\n", "text/csv")})
    assert r.status_code == 422 and r.json()["error"] == "STATEMENT_PARSE_ERROR"


def test_manual_review_and_analyst_decision(api, run_pipeline):
    h = login(api, "sever@demo.ru")
    app_id = create_and_submit(api, h, product_code="WORKING_CAPITAL", amount=1_500_000, term_months=12)
    run_pipeline()
    assert get(api, h, app_id)["status"]["code"] == "MANUAL_REVIEW"

    ha = login(api, "analyst@demo.ru")
    queue = api.get("/api/analyst/applications", params={"status": "MANUAL_REVIEW"}, headers=ha).json()
    assert any(x["id"] == app_id for x in queue)
    full = api.get(f"/api/analyst/applications/{app_id}", headers=ha).json()
    assert full["score"] == 50 and {c["source"] for c in full["checks"]} == {"EGRUL", "FNS", "BKI"}
    assert full["allowed_actions"] == ["APPROVE", "COUNTER_OFFER", "REJECT", "REQUEST_INFO"]

    stale = api.post(f"/api/analyst/applications/{app_id}/decision", headers=ha,
                     json={"action": "APPROVE", "version": full["version"] - 1, "comment": "ok ok"})
    assert stale.status_code == 409

    r = api.post(f"/api/analyst/applications/{app_id}/decision", headers=ha,
                 json={"action": "APPROVE", "version": full["version"], "comment": "Подтверждены контракты на 2027 год"})
    assert r.status_code == 200, r.text
    assert r.json()["status"]["code"] == "APPROVED"
    audit = [e for e in r.json()["events"] if e["actor_type"] == "ANALYST"]
    assert audit and audit[-1]["reason"] == "Подтверждены контракты на 2027 год"


def test_analyst_request_info(api, run_pipeline):
    h = login(api, "sever@demo.ru")
    app_id = create_and_submit(api, h, product_code="WORKING_CAPITAL", amount=1_000_000, term_months=12)
    run_pipeline()
    ha = login(api, "analyst@demo.ru")
    full = api.get(f"/api/analyst/applications/{app_id}", headers=ha).json()
    r = api.post(f"/api/analyst/applications/{app_id}/decision", headers=ha, json={
        "action": "REQUEST_INFO", "version": full["version"], "comment": "Нужны договоры",
        "requested_items": ["Приложите действующие договоры подряда"]})
    assert r.json()["status"]["code"] == "NEED_INFO"
    a = get(api, h, app_id)
    assert a["missing_items"][0]["text"] == "Приложите действующие договоры подряда"
    upcoming = [step["status"] for step in a["timeline"] if step["state"] == "upcoming"]
    assert upcoming == ["MANUAL_REVIEW", "DECISION", "SIGNING", "ISSUED"]
    assert api.post(f"/api/applications/{app_id}/resubmit", headers=h).status_code == 409
    r = api.post(f"/api/applications/{app_id}/documents", headers=h, data={"kind": "OTHER"},
                 files={"file": ("contract.pdf", b"%PDF-1.4 synthetic contract", "application/pdf")})
    assert r.status_code == 201, r.text
    r = api.post(f"/api/applications/{app_id}/resubmit", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"]["code"] == "MANUAL_REVIEW"
    assert r.json()["missing_items"] is None
    run_pipeline()
    assert get(api, h, app_id)["status"]["code"] == "MANUAL_REVIEW"


def test_overdue_rejected(api, run_pipeline):
    h = login(api, "vector@demo.ru")
    app_id = create_and_submit(api, h, product_code="WORKING_CAPITAL", amount=3_000_000, term_months=12)
    run_pipeline()
    a = get(api, h, app_id)
    assert a["status"]["code"] == "REJECTED"
    assert a["allowed_actions"] == []


def test_liquidated_rejected_before_scoring(api, run_pipeline):
    h = login(api, "zakat@demo.ru")
    app_id = create_and_submit(api, h, product_code="WORKING_CAPITAL", amount=500_000, term_months=6)
    run_pipeline()
    a = get(api, h, app_id)
    assert a["status"]["code"] == "REJECTED"
    assert "SCORING" not in [t["status"] for t in a["timeline"]]


def test_bki_unavailable_goes_to_manual_review(api, run_pipeline):
    h = login(api, "tikhonova@demo.ru")
    app_id = create_and_submit(api, h, product_code="OVERDRAFT", amount=300_000, term_months=12, purpose="CASH_GAP")
    run_pipeline()
    assert get(api, h, app_id)["status"]["code"] == "MANUAL_REVIEW"
    ha = login(api, "analyst@demo.ru")
    full = api.get(f"/api/analyst/applications/{app_id}", headers=ha).json()
    assert len([e for e in full["events"] if e["event_type"] == "INTEGRATION_RETRY"]) == 2
    assert "BKI" in full["decision"]["recommendation"]


def test_security_and_guards(api):
    h = login(api, "anna@demo.ru")
    r = api.post("/api/applications", headers=h, json={"product_code": "WORKING_CAPITAL", "amount": 99_000_000,
                                                        "term_months": 12})
    assert r.status_code == 422
    body = {"product_code": "OVERDRAFT", "amount": 200_000, "term_months": 12}
    a1 = api.post("/api/applications", headers=h | {"Idempotency-Key": "k-1"}, json=body).json()
    a2 = api.post("/api/applications", headers=h | {"Idempotency-Key": "k-1"}, json=body).json()
    assert a1["id"] == a2["id"]
    assert api.post(f"/api/applications/{a1['id']}/accept", headers=h).status_code == 409
    assert api.post(f"/api/applications/{a1['id']}/submit", headers=h, json={"consent": False}).status_code == 422
    other = login(api, "vector@demo.ru")
    assert api.get(f"/api/applications/{a1['id']}", headers=other).status_code == 404
    assert api.get("/api/analyst/applications", headers=h).status_code == 403
    ha = login(api, "analyst@demo.ru")
    assert api.post("/api/applications", headers=ha, json=body).status_code == 403
    r = api.post(f"/api/applications/{a1['id']}/documents", headers=h, data={"kind": "OTHER"},
                 files={"file": ("x.exe", b"MZ", "application/x-msdownload")})
    assert r.status_code == 415


def test_stats(api):
    ha = login(api, "analyst@demo.ru")
    s = api.get("/api/analyst/stats", headers=ha).json()
    assert s["total"] >= 1 and "by_status" in s


def test_worker_repeated_error_goes_to_manual_review(api, monkeypatch):
    from app import worker
    from app.config import get_settings

    h = login(api, "anna@demo.ru")
    app_id = create_and_submit(api, h, product_code="WORKING_CAPITAL", amount=500_000, term_months=12)
    original = worker.process_step

    def fail_target(db, application, client):
        if application.id == app_id:
            raise RuntimeError("synthetic failure")
        return original(db, application, client)

    monkeypatch.setattr(worker, "process_step", fail_target)
    monkeypatch.setattr(get_settings(), "pipeline_error_retry_delay_sec", 0)
    for _ in range(3):
        worker.run_once(batch=1)
    a = get(api, h, app_id)
    assert a["status"]["code"] == "MANUAL_REVIEW"
    ha = login(api, "analyst@demo.ru")
    full = api.get(f"/api/analyst/applications/{app_id}", headers=ha).json()
    errors = [e for e in full["events"] if e["event_type"] == "PIPELINE_ERROR"]
    assert [e["payload"]["attempt"] for e in errors] == [1, 2, 3]
    assert not any("synthetic failure" in str(e) for e in errors)
    worker.run_once(batch=1)
    assert get(api, h, app_id)["status"]["code"] == "MANUAL_REVIEW"
