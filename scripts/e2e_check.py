"""Сквозная проверка всех сценариев через HTTP API работающей системы.

Запуск (система должна быть поднята):
    python scripts/e2e_check.py --base http://localhost:8080
Проходит все персоны, проверяет итоговые статусы и печатает отчёт. Код выхода 1 при ошибке.
"""
import argparse
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "demo2026"
WAIT_STATUSES = {"SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING"}


class Api:
    def __init__(self, base: str, email: str):
        self.c = httpx.Client(base_url=base, timeout=30)
        r = self.c.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        r.raise_for_status()
        self.c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    def __getattr__(self, name):
        return getattr(self.c, name)

    def ok(self, r: httpx.Response) -> dict:
        if r.status_code >= 400:
            raise AssertionError(f"{r.request.method} {r.request.url} → {r.status_code}: {r.text}")
        return r.json() if r.content else {}

    def wait(self, app_id: int, timeout: float = 60) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            a = self.ok(self.get(f"/api/applications/{app_id}"))
            if a["status"]["code"] not in WAIT_STATUSES:
                return a
            time.sleep(0.5)
        raise AssertionError(f"Заявка {app_id} зависла в статусе {a['status']['code']}")

    def apply(self, product: str, amount: int, term: int, purpose: str, collateral: dict | None = None) -> dict:
        body = {"product_code": product, "amount": amount, "term_months": term, "purpose": purpose}
        if collateral:
            body["collateral"] = collateral
        a = self.ok(self.post("/api/applications", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}))
        self.ok(self.post(f"/api/applications/{a['id']}/submit", json={"consent": True}))
        return self.wait(a["id"])


def expect(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def scenario_approved(base):
    api = Api(base, "anna@demo.ru")
    a = api.apply("WORKING_CAPITAL", 2_000_000, 12, "PURCHASE_GOODS")
    expect(a["status"]["code"] == "APPROVED", f"ожидали APPROVED, получили {a['status']['code']}")
    a = api.ok(api.post(f"/api/applications/{a['id']}/accept"))
    expect(a["status"]["code"] == "SIGNING", "после принятия ждём SIGNING")
    a = api.ok(api.post(f"/api/applications/{a['id']}/sign", json={"confirm": True, "signer_name": "Смирнова А. С."}))
    expect(a["status"]["code"] == "ISSUED", "после подписи ждём ISSUED")
    return f"{a['number']}: APPROVED → SIGNING → ISSUED, ставка {a['agreement']['rate']}%"


def scenario_counter(base):
    api = Api(base, "start@demo.ru")
    a = api.apply("WORKING_CAPITAL", 5_000_000, 24, "EXPANSION")
    expect(a["status"]["code"] == "COUNTER_OFFER", f"ожидали COUNTER_OFFER, получили {a['status']['code']}")
    offer = a["decision"]["offer"]
    expect(offer["amount"] < 5_000_000, "контрпредложение должно быть меньше запроса")
    b = api.apply("EQUIPMENT", 1_000_000, 24, "EQUIPMENT",
                  {"equipment_name": "Серверы", "equipment_cost": 1_200_000})
    # молодой бизнес: кредит на оборудование недоступен → альтернативный продукт (или дозапрос счёта)
    return f"{a['number']}: COUNTER_OFFER {offer['amount']:,} ₽ вместо 5 000 000 ₽; оборудование → {b['status']['code']}"


def scenario_need_info(base):
    api = Api(base, "kovalev@demo.ru")
    a = api.apply("EQUIPMENT", 1_800_000, 36, "EQUIPMENT")
    expect(a["status"]["code"] == "NEED_INFO", f"ожидали NEED_INFO, получили {a['status']['code']}")
    codes = {i["code"] for i in a["missing_items"]}
    expect({"STATEMENT", "EQUIPMENT_INFO", "EQUIPMENT_INVOICE"} <= codes, f"не тот список дозапроса: {codes}")
    # короткая выписка — ошибки нет, но месяцев мало
    api.ok(api.patch(f"/api/applications/{a['id']}", json={
        "collateral": {"equipment_name": "Фрезерный станок с ЧПУ", "equipment_cost": 2_000_000, "supplier": "ООО «СтанкоТорг»"}}))
    with open(ROOT / "test-data/statement_kovalev_6m.csv", "rb") as f:
        a = api.ok(api.post(f"/api/applications/{a['id']}/documents", data={"kind": "STATEMENT"},
                            files={"file": ("statement.csv", f, "text/csv")}))
    expect(a["financials"]["months_count"] == 6, "выписка должна распознаться в 6 месяцев")
    with open(ROOT / "test-data/invoice_cnc_machine.pdf", "rb") as f:
        api.ok(api.post(f"/api/applications/{a['id']}/documents", data={"kind": "EQUIPMENT_INVOICE"},
                        files={"file": ("invoice.pdf", f, "application/pdf")}))
    api.ok(api.post(f"/api/applications/{a['id']}/resubmit"))
    a = api.wait(a["id"])
    expect(a["status"]["code"] == "APPROVED", f"после дозапроса ждём APPROVED, получили {a['status']['code']}")
    return f"{a['number']}: NEED_INFO → выписка распознана ({a['financials']['avg_monthly_inflow']:,.0f} ₽/мес) → APPROVED"


def scenario_manual(base):
    api = Api(base, "sever@demo.ru")
    a = api.apply("WORKING_CAPITAL", 1_500_000, 12, "CASH_GAP")
    expect(a["status"]["code"] == "MANUAL_REVIEW", f"ожидали MANUAL_REVIEW, получили {a['status']['code']}")
    an = Api(base, "analyst@demo.ru")
    full = an.ok(an.get(f"/api/analyst/applications/{a['id']}"))
    expect(full["score"] is not None and full["score_details"]["factors"], "аналитик должен видеть скоринг")
    expect(len(full["checks"]) >= 3, "аналитик должен видеть результаты проверок")
    # конфликт версий
    r = an.post(f"/api/analyst/applications/{a['id']}/decision",
                json={"action": "APPROVE", "version": full["version"] - 1, "comment": "проверка конфликта"})
    expect(r.status_code == 409, "устаревшая версия должна давать 409")
    full = an.ok(an.post(f"/api/analyst/applications/{a['id']}/decision", json={
        "action": "COUNTER_OFFER", "version": full["version"], "amount": 1_200_000, "term_months": 12,
        "comment": "Сезонность выручки в строительстве: снижаем сумму до 1,2 млн."}))
    expect(full["status"]["code"] == "COUNTER_OFFER", "после решения аналитика ждём COUNTER_OFFER")
    c = api.ok(api.get(f"/api/applications/{a['id']}"))
    expect("score_details" not in c and "rules_fired" not in (c["decision"] or {}), "клиенту не показываем веса и правила")
    return f"{a['number']}: MANUAL_REVIEW (балл {full['score']}) → аналитик → COUNTER_OFFER 1 200 000 ₽"


def scenario_overdue(base):
    api = Api(base, "vector@demo.ru")
    a = api.apply("WORKING_CAPITAL", 3_000_000, 12, "PURCHASE_GOODS")
    expect(a["status"]["code"] == "REJECTED", f"ожидали REJECTED, получили {a['status']['code']}")
    expect(any("просрочка" in r["text"] for r in a["decision"]["reasons"]), "в причинах должна быть просрочка")
    return f"{a['number']}: REJECTED (стоп-фактор: текущая просрочка)"


def scenario_term_extension(base):
    """Same principal, longer term; the lower payment must disclose the higher total cost."""
    api = Api(base, "start@demo.ru")
    a = api.apply("WORKING_CAPITAL", 2_500_000, 6, "PURCHASE_GOODS")
    expect(a["status"]["code"] == "COUNTER_OFFER", "ожидали альтернативный срок")
    offer = a["decision"]["offer"]
    requested = a["decision"]["requested_terms"]
    expect(offer["amount"] == 2_500_000 and offer["term_months"] == 9, "ожидали ту же сумму на 9 вместо 6 месяцев")
    expect(requested["monthly_payment"] > offer["monthly_payment"], "платёж должен уменьшиться")
    expect(requested["monthly_payment"] * 6 < offer["monthly_payment"] * 9, "общие выплаты должны увеличиться")
    an = Api(base, "analyst@demo.ru")
    full = an.ok(an.get(f"/api/analyst/applications/{a['id']}"))
    expect(full["decision"]["limits"]["dti"] < 2_500_000, "запрос не проходит исходный DTI")
    expect(min(full["decision"]["offer_limits"].values()) >= 2_500_000, "предложение должно проходить все лимиты")
    expect("limits" not in a["decision"] and "offer_limits" not in a["decision"], "внутренние лимиты не показываем клиенту")
    return f"{a['number']}: 2 500 000 ₽, 6 → 9 мес.; платёж {requested['monthly_payment']:,.2f} → {offer['monthly_payment']:,.2f} ₽; общая стоимость выше"


def scenario_analyst_request(base):
    """A manual request cannot be bypassed; a second request needs another new upload."""
    api = Api(base, "sever@demo.ru")
    a = api.apply("WORKING_CAPITAL", 1_000_000, 12, "PURCHASE_GOODS")
    expect(a["status"]["code"] == "MANUAL_REVIEW", "заявка должна попасть специалисту")
    an = Api(base, "analyst@demo.ru")
    for round_number in (1, 2):
        full = an.ok(an.get(f"/api/analyst/applications/{a['id']}"))
        an.ok(an.post(f"/api/analyst/applications/{a['id']}/decision", json={
            "action": "REQUEST_INFO", "version": full["version"],
            "comment": f"Проверка ответа на ручной запрос, раунд {round_number}",
            "requested_items": ["Приложите синтетический документ для проверки"]}))
        expect(api.post(f"/api/applications/{a['id']}/resubmit").status_code == 409,
               "старые документы не должны закрывать новый запрос")
        with open(ROOT / "test-data/invoice_cnc_machine.pdf", "rb") as f:
            api.ok(api.post(f"/api/applications/{a['id']}/documents", data={"kind": "OTHER"},
                            files={"file": (f"response-{round_number}.pdf", f, "application/pdf")}))
        a = api.ok(api.post(f"/api/applications/{a['id']}/resubmit"))
        expect(a["status"]["code"] == "MANUAL_REVIEW" and a["missing_items"] is None,
               "ответ должен вернуться специалисту, без автоодобрения")
    full = an.ok(an.get(f"/api/analyst/applications/{a['id']}"))
    responses = [e for e in full["events"] if e["event_type"] == "STATUS_CHANGED"
                 and e["from_status"] == "NEED_INFO" and e["to_status"] == "MANUAL_REVIEW"]
    expect(len(responses) == 2, "аудит должен содержать оба ответа")
    return f"{a['number']}: два ручных дозапроса, 409 без новых документов, оба ответа → MANUAL_REVIEW"


def scenario_liquidated(base):
    api = Api(base, "zakat@demo.ru")
    a = api.apply("WORKING_CAPITAL", 500_000, 6, "CASH_GAP")
    expect(a["status"]["code"] == "REJECTED", f"ожидали REJECTED, получили {a['status']['code']}")
    statuses = [t["status"] for t in a["timeline"] if t["state"] != "upcoming"]
    expect("SCORING" not in statuses, "ликвидированная компания отсекается до скоринга")
    return f"{a['number']}: REJECTED на этапе проверки в реестре (без скоринга)"


def scenario_bki_down(base):
    api = Api(base, "tikhonova@demo.ru")
    a = api.apply("OVERDRAFT", 300_000, 12, "CASH_GAP")
    expect(a["status"]["code"] == "MANUAL_REVIEW", f"ожидали MANUAL_REVIEW, получили {a['status']['code']}")
    an = Api(base, "analyst@demo.ru")
    full = an.ok(an.get(f"/api/analyst/applications/{a['id']}"))
    retries = [e for e in full["events"] if e["event_type"] == "INTEGRATION_RETRY"]
    expect(len(retries) >= 1, "должны быть ретраи интеграции")
    return f"{a['number']}: БКИ недоступно → {len(retries)} повтор(а) → MANUAL_REVIEW"


def scenario_guards(base):
    api = Api(base, "anna@demo.ru")
    r = api.post("/api/applications", json={"product_code": "WORKING_CAPITAL", "amount": 50_000_000, "term_months": 12})
    expect(r.status_code == 422, "сумма вне лимитов продукта → 422")
    key = uuid.uuid4().hex
    body = {"product_code": "WORKING_CAPITAL", "amount": 500_000, "term_months": 6}
    a1 = api.ok(api.post("/api/applications", json=body, headers={"Idempotency-Key": key}))
    a2 = api.ok(api.post("/api/applications", json=body, headers={"Idempotency-Key": key}))
    expect(a1["id"] == a2["id"], "повтор с тем же Idempotency-Key не должен создавать дубль")
    r = api.post(f"/api/applications/{a1['id']}/sign", json={"confirm": True, "signer_name": "Тест Тестов"})
    expect(r.status_code == 409, "подписать черновик нельзя → 409")
    other = Api(base, "vector@demo.ru")
    expect(other.get(f"/api/applications/{a1['id']}").status_code == 404, "чужая заявка не видна")
    expect(api.get("/api/analyst/applications").status_code == 403, "клиенту недоступен кабинет аналитика")
    api.ok(api.post(f"/api/applications/{a1['id']}/cancel", json={"reason": "тест"}))
    return "лимиты продукта, идемпотентность, запрет недопустимых переходов, изоляция клиентов, RBAC"


SCENARIOS = [scenario_approved, scenario_counter, scenario_need_info, scenario_manual,
             scenario_overdue, scenario_liquidated, scenario_bki_down, scenario_guards,
             scenario_term_extension, scenario_analyst_request]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--scenario", action="append", choices=[s.__name__ for s in SCENARIOS],
                    help="Run only a named scenario; repeat to select several")
    args = ap.parse_args()
    selected = [s for s in SCENARIOS if not args.scenario or s.__name__ in args.scenario]
    failed = 0
    for s in selected:
        try:
            print(f"✅ {s.__name__}: {s(args.base)}")
        except AssertionError as e:
            failed += 1
            print(f"❌ {s.__name__}: {e}")
    print(f"\n{len(selected) - failed}/{len(selected)} сценариев пройдено")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
