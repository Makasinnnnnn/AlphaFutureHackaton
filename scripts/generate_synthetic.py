"""Генератор синтетических данных (детерминированный, без случайности между запусками).

Создаёт:
- data/synthetic/companies.json — компании-персоны: данные реестра (ЕГРЮЛ/ЕГРИП),
  сведения ФНС «Прозрачный бизнес», отчёт БКИ, обороты по счёту в банке;
- test-data/*.csv — выписки из «другого банка» для клиентов без счёта в банке.

Все ИНН, ОГРН, ФИО и суммы вымышлены. Запуск: python scripts/generate_synthetic.py
"""
import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 10, 20)


def months_back(n: int, end: date = TODAY) -> list[str]:
    """n последних полных месяцев, по возрастанию."""
    y, m = end.year, end.month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y:04d}-{m:02d}")
    return list(reversed(out))


def turnovers(months: list[str], base: float, wiggle: list[float], outflow_share: float) -> list[dict]:
    rows = []
    for i, mo in enumerate(months):
        k = wiggle[i % len(wiggle)]
        inflow = round(base * k, -3)
        rows.append({"month": mo, "inflow": inflow, "outflow": round(inflow * outflow_share, -3)})
    return rows


STABLE = [1.00, 0.97, 1.03, 0.98, 1.04, 0.99, 1.02, 0.96, 1.01, 1.03, 0.98, 1.00]
GROWING = [0.92, 0.95, 0.98, 1.00, 1.02, 1.04, 1.05, 1.03, 1.06, 1.08, 1.04, 1.00]
VOLATILE = [1.30, 0.78, 1.15, 0.72, 1.25, 0.85, 1.20, 0.80, 1.10, 0.90, 1.28, 0.75]

COMPANIES = [
    {
        "persona": "APPROVED",
        "user": {"email": "anna@demo.ru", "full_name": "Смирнова Анна Сергеевна", "position": "Индивидуальный предприниматель"},
        "egrul": {
            "inn": "701712345678", "ogrn": "319701700012345", "legal_form": "IP",
            "name": "ИП Смирнова Анна Сергеевна (кофейни «Зерно»)", "status": "ACTIVE",
            "registered_at": "2019-03-15", "okved": "56.10",
            "okved_name": "Деятельность ресторанов и услуги по доставке продуктов питания",
            "address": "634050, г. Томск, пр-т Ленина, д. 40", "director": "Смирнова Анна Сергеевна",
        },
        "fns": {"mass_address": False, "tax_arrears": 0, "disqualified_director": False,
                "employees_count": 14, "tax_regime": "УСН", "founders": []},
        "bki": {"has_history": True, "current_overdue_days": 0, "max_overdue_days_12m": 0,
                "obligations": [{"type": "Кредит на развитие", "creditor": "Банк-1", "opened_at": "2024-02-01",
                                 "amount": 1200000, "balance": 520000, "monthly_payment": 40000, "status": "ACTIVE"},
                                {"type": "Кредитная карта", "creditor": "Банк-2", "opened_at": "2021-06-10",
                                 "amount": 300000, "balance": 0, "monthly_payment": 0, "status": "CLOSED"}],
                "inquiries_30d": 0},
        "bank": {"is_client": True, "turnovers": ("STABLE", 2_000_000, 12, 0.85)},
    },
    {
        "persona": "COUNTER_OFFER",
        "user": {"email": "start@demo.ru", "full_name": "Петров Игорь Алексеевич", "position": "Генеральный директор"},
        "egrul": {
            "inn": "7017111222", "ogrn": "1257000012345", "legal_form": "OOO",
            "name": "ООО «Новый старт»", "status": "ACTIVE", "registered_at": "2025-12-10", "okved": "62.01",
            "okved_name": "Разработка компьютерного программного обеспечения",
            "address": "634029, г. Томск, ул. Белинского, д. 15, оф. 301", "director": "Петров Игорь Алексеевич",
        },
        "fns": {"mass_address": False, "tax_arrears": 0, "disqualified_director": False,
                "employees_count": 6, "tax_regime": "УСН", "founders": [{"name": "Петров Игорь Алексеевич", "share": 100}]},
        "bki": {"has_history": False, "current_overdue_days": 0, "max_overdue_days_12m": 0, "obligations": [],
                "inquiries_30d": 1},
        "bank": {"is_client": True, "turnovers": ("STABLE", 650_000, 9, 0.8)},
    },
    {
        "persona": "NEED_INFO",
        "user": {"email": "kovalev@demo.ru", "full_name": "Ковалёв Дмитрий Андреевич", "position": "Индивидуальный предприниматель"},
        "egrul": {
            "inn": "701798765432", "ogrn": "320701700054321", "legal_form": "IP",
            "name": "ИП Ковалёв Дмитрий Андреевич (столярная мастерская)", "status": "ACTIVE",
            "registered_at": "2020-06-01", "okved": "16.23",
            "okved_name": "Производство прочих деревянных строительных конструкций и столярных изделий",
            "address": "634021, г. Томск, ул. Елизаровых, д. 79", "director": "Ковалёв Дмитрий Андреевич",
        },
        "fns": {"mass_address": False, "tax_arrears": 0, "disqualified_director": False,
                "employees_count": 5, "tax_regime": "Патент", "founders": []},
        "bki": {"has_history": True, "current_overdue_days": 0, "max_overdue_days_12m": 0,
                "obligations": [{"type": "Автокредит", "creditor": "Банк-3", "opened_at": "2023-09-01",
                                 "amount": 1500000, "balance": 610000, "monthly_payment": 35000, "status": "ACTIVE"}],
                "inquiries_30d": 0},
        "bank": {"is_client": False},
        "statement": ("statement_kovalev_6m.csv", 900_000, [1.10, 0.85, 1.20, 0.80, 1.05, 1.00]),
    },
    {
        "persona": "MANUAL_REVIEW",
        "user": {"email": "sever@demo.ru", "full_name": "Лебедева Марина Олеговна", "position": "Финансовый директор"},
        "egrul": {
            "inn": "7017222333", "ogrn": "1227000005678", "legal_form": "OOO",
            "name": "ООО «Северный край»", "status": "ACTIVE", "registered_at": "2022-05-20", "okved": "41.20",
            "okved_name": "Строительство жилых и нежилых зданий",
            "address": "634009, г. Томск, ул. Карла Маркса, д. 7", "director": "Громов Сергей Павлович",
        },
        "fns": {"mass_address": False, "tax_arrears": 0, "disqualified_director": False,
                "employees_count": 23, "tax_regime": "ОСН", "founders": [{"name": "Громов Сергей Павлович", "share": 60},
                                                                        {"name": "Лебедева Марина Олеговна", "share": 40}]},
        "bki": {"has_history": True, "current_overdue_days": 0, "max_overdue_days_12m": 12,
                "obligations": [{"type": "Кредит на пополнение оборотных средств", "creditor": "Банк-1",
                                 "opened_at": "2025-03-01", "amount": 4000000, "balance": 2300000,
                                 "monthly_payment": 240000, "status": "ACTIVE"}],
                "inquiries_30d": 2},
        "bank": {"is_client": True, "turnovers": ("SEMI", 1_200_000, 12, 0.9)},
    },
    {
        "persona": "REJECTED_OVERDUE",
        "user": {"email": "vector@demo.ru", "full_name": "Сидоров Олег Николаевич", "position": "Генеральный директор"},
        "egrul": {
            "inn": "7017456789", "ogrn": "1167000098765", "legal_form": "OOO",
            "name": "ООО «Вектор Логистик»", "status": "ACTIVE", "registered_at": "2016-09-01", "okved": "49.41",
            "okved_name": "Деятельность автомобильного грузового транспорта",
            "address": "634034, г. Томск, ул. Красноармейская, д. 101", "director": "Сидоров Олег Николаевич",
        },
        "fns": {"mass_address": False, "tax_arrears": 85000, "disqualified_director": False,
                "employees_count": 31, "tax_regime": "ОСН", "founders": [{"name": "Сидоров Олег Николаевич", "share": 100}]},
        "bki": {"has_history": True, "current_overdue_days": 47, "max_overdue_days_12m": 47,
                "obligations": [{"type": "Лизинг", "creditor": "Лизинговая компания-1", "opened_at": "2023-04-01",
                                 "amount": 6000000, "balance": 3100000, "monthly_payment": 210000, "status": "OVERDUE"}],
                "inquiries_30d": 4},
        "bank": {"is_client": True, "turnovers": ("VOLATILE", 3_000_000, 12, 0.97)},
    },
    {
        "persona": "REJECTED_LIQUIDATED",
        "user": {"email": "zakat@demo.ru", "full_name": "Иванов Пётр Сергеевич", "position": "Директор"},
        "egrul": {
            "inn": "7017000013", "ogrn": "1137000000013", "legal_form": "OOO",
            "name": "ООО «Закат»", "status": "LIQUIDATED", "registered_at": "2013-02-11", "okved": "47.19",
            "okved_name": "Торговля розничная прочая в неспециализированных магазинах",
            "address": "634061, г. Томск, ул. Никитина, д. 3", "director": "Иванов Пётр Сергеевич",
            "liquidated_at": "2026-08-01",
        },
        "fns": {"mass_address": True, "tax_arrears": 0, "disqualified_director": False,
                "employees_count": 0, "tax_regime": "УСН", "founders": []},
        "bki": {"has_history": True, "current_overdue_days": 0, "max_overdue_days_12m": 0, "obligations": [],
                "inquiries_30d": 0},
        "bank": {"is_client": True, "turnovers": ("STABLE", 400_000, 12, 0.95)},
    },
    {
        "persona": "BKI_UNAVAILABLE",
        "user": {"email": "tikhonova@demo.ru", "full_name": "Тихонова Ольга Викторовна", "position": "Индивидуальный предприниматель"},
        "egrul": {
            "inn": "701755500011", "ogrn": "318701700077777", "legal_form": "IP",
            "name": "ИП Тихонова Ольга Викторовна (магазин одежды)", "status": "ACTIVE",
            "registered_at": "2018-11-01", "okved": "47.71",
            "okved_name": "Торговля розничная одеждой в специализированных магазинах",
            "address": "634045, г. Томск, ул. Красноармейская, д. 156", "director": "Тихонова Ольга Викторовна",
        },
        "fns": {"mass_address": False, "tax_arrears": 0, "disqualified_director": False,
                "employees_count": 4, "tax_regime": "УСН", "founders": []},
        "bki": {"simulate": "UNAVAILABLE"},
        "bank": {"is_client": True, "turnovers": ("STABLE", 1_100_000, 12, 0.9)},
    },
]

SEMI = [1.20, 0.82, 1.10, 0.95, 1.30, 0.88, 1.25, 0.80, 1.10, 0.75, 1.20, 0.90]
PATTERNS = {"STABLE": STABLE, "GROWING": GROWING, "VOLATILE": VOLATILE, "SEMI": SEMI}


def write_statement(filename: str, base: float, factors: list[float]) -> None:
    """Выписка «из другого банка»: отдельные операции, формат Дата;Приход;Расход;Назначение."""
    months = months_back(len(factors))
    path = ROOT / "test-data" / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Дата", "Приход", "Расход", "Назначение платежа"])
        for mo, k in zip(months, factors):
            y, m = map(int, mo.split("-"))
            total_in = round(base * k, -3)
            parts = [0.35, 0.25, 0.2, 0.2]
            for i, share in enumerate(parts):
                d = date(y, m, 3 + i * 7)
                w.writerow([d.strftime("%d.%m.%Y"), f"{total_in * share:.2f}".replace(".", ","), "",
                            f"Оплата по счёту №{m}{i + 1:02d} за изделия из дерева"])
            for i, (share, what) in enumerate([(0.45, "Закупка пиломатериалов"), (0.2, "Аренда цеха"),
                                               (0.15, "Зарплата"), (0.04, "Платёж по автокредиту")]):
                d = date(y, m, 5 + i * 6)
                w.writerow([d.strftime("%d.%m.%Y"), "", f"{total_in * share:.2f}".replace(".", ","), what])
    print("wrote", path.relative_to(ROOT))


def main() -> None:
    out = []
    for c in COMPANIES:
        rec = {k: v for k, v in c.items() if k not in ("bank", "statement")}
        bank = c["bank"]
        if bank.get("is_client"):
            pattern, base, n, share = bank["turnovers"]
            rec["bank"] = {"is_client": True, "turnovers": turnovers(months_back(n), base, PATTERNS[pattern], share)}
        else:
            rec["bank"] = {"is_client": False, "turnovers": []}
        if c.get("bki", {}).get("obligations") is not None:
            rec["bki"]["total_monthly_payments"] = sum(o["monthly_payment"] for o in c["bki"]["obligations"]
                                                       if o["status"] != "CLOSED")
        out.append(rec)
        if c.get("statement"):
            write_statement(*c["statement"])

    (ROOT / "data" / "synthetic").mkdir(parents=True, exist_ok=True)
    path = ROOT / "data" / "synthetic" / "companies.json"
    path.write_text(json.dumps({"generated_for": TODAY.isoformat(), "companies": out}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print("wrote", path.relative_to(ROOT))

    # Короткая выписка (2 месяца) — для проверки ошибки «мало данных»
    write_statement("statement_too_short.csv", 500_000, [1.0, 1.1])


if __name__ == "__main__":
    main()
