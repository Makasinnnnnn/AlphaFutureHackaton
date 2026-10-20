# Модель данных

PostgreSQL 16. Схема создаётся миграциями Alembic (`backend/alembic/versions`). Гибкие части заявки (обороты, залог, решение, договор, детализация скоринга) хранятся в JSONB — их структура меняется чаще, чем ядро заявки, и не требует миграций на каждое изменение правил.

```mermaid
erDiagram
    COMPANIES ||--o{ USERS : "представители"
    COMPANIES ||--o{ ACCOUNT_TURNOVERS : "обороты по счёту"
    COMPANIES ||--o{ APPLICATIONS : "заявки"
    USERS ||--o{ APPLICATIONS : "заявитель"
    PRODUCTS ||--o{ APPLICATIONS : "продукт"
    APPLICATIONS ||--o{ APPLICATION_EVENTS : "аудит"
    APPLICATIONS ||--o{ EXTERNAL_CHECKS : "проверки"
    APPLICATIONS ||--o{ DOCUMENTS : "документы"
    USERS ||--o{ NOTIFICATIONS : "уведомления"

    COMPANIES {
        varchar inn PK "ИНН"
        varchar name
        varchar legal_form "IP | OOO"
        varchar ogrn
        varchar okved
        varchar address
        varchar director
        date registered_at
        varchar registry_status "ACTIVE | LIQUIDATED"
        bool is_bank_client
        timestamptz registry_synced_at
    }
    USERS {
        int id PK
        varchar email UK
        varchar password_hash "bcrypt"
        varchar role "CLIENT | ANALYST"
        varchar full_name
        varchar position
        varchar company_inn FK
    }
    ACCOUNT_TURNOVERS {
        int id PK
        varchar company_inn FK
        varchar month "YYYY-MM"
        numeric inflow
        numeric outflow
    }
    PRODUCTS {
        varchar code PK
        varchar name
        jsonb purposes
        numeric min_amount
        numeric max_amount
        int min_term_months
        int max_term_months
        numeric base_rate
        bool requires_collateral
        jsonb rules "пороги решения"
    }
    APPLICATIONS {
        int id PK
        varchar number UK "CR-2026-000001"
        varchar company_inn FK
        int applicant_id FK
        varchar product_code FK
        varchar purpose
        numeric amount
        int term_months
        jsonb collateral
        jsonb financials "источник + помесячные обороты"
        varchar status
        jsonb missing_items
        int score
        varchar score_grade
        jsonb score_details
        jsonb decision "оффер, причины, правила"
        jsonb agreement "договор, график, подпись"
        timestamptz next_action_at "для воркера"
        int enrichment_attempts
        varchar idempotency_key "уникален в паре с applicant_id"
        int version "оптимистическая блокировка"
    }
    APPLICATION_EVENTS {
        bigint id PK
        int application_id FK
        varchar event_type
        varchar from_status
        varchar to_status
        varchar actor_type "CLIENT | ANALYST | SYSTEM"
        int actor_id
        text reason
        jsonb payload
        timestamptz created_at
    }
    EXTERNAL_CHECKS {
        bigint id PK
        int application_id FK
        varchar source "EGRUL | FNS | BKI"
        varchar status "OK | NOT_FOUND | ERROR"
        int attempt
        int duration_ms
        jsonb response
        text error
    }
    DOCUMENTS {
        int id PK
        int application_id FK
        varchar kind "STATEMENT | EQUIPMENT_INVOICE | OTHER"
        varchar filename
        varchar content_type
        int size_bytes
        varchar sha256
        bytea content
        jsonb parsed "результат распознавания"
    }
    NOTIFICATIONS {
        int id PK
        int user_id FK
        int application_id FK
        varchar title
        text body
        bool is_read
    }
```

## Индексы и ограничения

| Объект | Зачем |
|---|---|
| `ix_applications_pipeline (status, next_action_at)` | Быстрый выбор заявок воркером. |
| `uq_application_idempotency (applicant_id, idempotency_key)` | Повтор `POST /applications` с тем же ключом не создаёт дубль. |
| `applications.version` | Оптимистическая блокировка (SQLAlchemy `version_id_col`). |
| `account_turnovers (company_inn, month)` UNIQUE | Один ряд оборотов на месяц. |
| Индексы по внешним ключам | Карточка заявки собирается за несколько запросов `selectin`. |

## Структуры JSONB

**`financials`**
```json
{
  "source": "BANK_ACCOUNT | STATEMENT_UPLOAD",
  "months": [{"month": "2026-04", "inflow": 990000, "outflow": 760000}],
  "months_count": 6,
  "avg_monthly_inflow": 900000,
  "annual_revenue_estimate": 10800000,
  "stability_cv": 0.14
}
```

**`decision`**
```json
{
  "outcome": "COUNTER_OFFER",
  "offer": {"product_code": "WORKING_CAPITAL", "amount": 3120000, "term_months": 24, "rate": 20.5, "monthly_payment": 159558.0},
  "reasons": [{"impact": "negative", "text": "Сумма великовата относительно выручки бизнеса."}],
  "limits": {"product_max": 5000000, "revenue": 3120000, "dti": 6355055},
  "rules_fired": ["LIMIT:revenue", "COUNTER"],
  "decided_by": "SYSTEM"
}
```
Клиент получает только `outcome`, `offer`, `reasons` и комментарий аналитика. `limits`, `rules_fired` и `score_details` доступны только аналитику.
