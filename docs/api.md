# API

- Swagger UI: http://localhost:8080/api/docs (или http://localhost:8000/api/docs напрямую)
- OpenAPI: [`docs/api/openapi.json`](api/openapi.json), генерируется из кода: `cd backend && python ../scripts/export_openapi.py`
- Коллекция запросов Postman: [`docs/api/postman_collection.json`](api/postman_collection.json) — папки идут в порядке сквозного сценария, токены и id заявки сохраняются в переменные автоматически.

## Общие правила

- Аутентификация: `POST /api/auth/login` → `access_token`, далее заголовок `Authorization: Bearer <token>`.
- Роли: `CLIENT` — только заявки своей компании (чужая заявка — `404`), `ANALYST` — очередь и решения.
- Ошибки в едином формате:
  ```json
  {"error": "INVALID_TRANSITION", "message": "Действие недоступно: заявка в статусе «Черновик».", "details": {...}, "request_id": "a1b2c3"}
  ```
  `400` бизнес-ошибка, `401` нет или истёк токен, `403` нет прав, `404` не найдено, `409` недопустимый переход или конфликт версий, `413` файл больше 5 МБ, `415` тип файла не поддерживается, `422` валидация.
- `X-Request-ID` возвращается в каждом ответе и пишется в логи — по нему ищется запрос.
- `Idempotency-Key` в `POST /api/applications` — повтор с тем же ключом вернёт ту же заявку.

## Эндпоинты

| Метод | Путь | Роль | Назначение |
|---|---|---|---|
| GET | `/health/live`, `/health/ready` | — | Пробы живости и готовности (БД + интеграции) |
| POST | `/api/auth/login` | — | Вход |
| GET | `/api/auth/me` | любая | Текущий пользователь |
| GET | `/api/auth/demo-accounts` | — | Тестовые учётки и их сценарии (пусто при `ENVIRONMENT=production`) |
| GET | `/api/companies/me` | CLIENT | Реквизиты компании, подтянутые из реестра по ИНН |
| GET | `/api/companies/me/financials` | CLIENT | Обороты по счёту в банке (если компания — клиент банка) |
| GET | `/api/products` | любая | Каталог продуктов |
| GET | `/api/products/purposes` | любая | Цели финансирования |
| POST | `/api/assistant/recommend` | любая | Подбор продукта по цели или свободному тексту |
| GET | `/api/applications` | CLIENT | Заявки компании |
| POST | `/api/applications` | CLIENT | Создать черновик |
| GET | `/api/applications/{id}` | CLIENT | Заявка: статус, маршрут, решение, договор, доступные действия |
| PATCH | `/api/applications/{id}` | CLIENT | Изменить черновик или дополнить заявку по запросу |
| POST | `/api/applications/{id}/submit` | CLIENT | Отправить в банк |
| POST | `/api/applications/{id}/resubmit` | CLIENT | Отправить после дозапроса |
| POST | `/api/applications/{id}/documents` | CLIENT | Загрузить документ (`multipart`: `kind`, `file`). Выписка распознаётся. |
| GET | `/api/applications/{id}/documents/{doc}` | CLIENT | Скачать документ |
| POST | `/api/applications/{id}/accept` | CLIENT | Принять предложение → договор |
| POST | `/api/applications/{id}/sign` | CLIENT | Подписать (симуляция) → выдача (симуляция) |
| POST | `/api/applications/{id}/cancel` | CLIENT | Отменить или отказаться |
| GET | `/api/analyst/applications?status=&q=` | ANALYST | Очередь с фильтрами и поиском |
| GET | `/api/analyst/applications/{id}` | ANALYST | Полная карточка: скоринг, проверки, аудит |
| POST | `/api/analyst/applications/{id}/decision` | ANALYST | Решение: `APPROVE`, `COUNTER_OFFER`, `REJECT`, `REQUEST_INFO` |
| GET | `/api/analyst/stats` | ANALYST | Сводка: статусы, доля одобрений, время до решения |
| GET | `/api/notifications` | любая | Уведомления в кабинете |
| POST | `/api/notifications/read-all` | любая | Отметить прочитанными |

Поле `allowed_actions` в ответе заявки перечисляет действия, доступные в текущем статусе (`SUBMIT`, `RESUBMIT`, `ACCEPT_OFFER`, `SIGN`, `CANCEL`…). Интерфейс опирается на него, а не дублирует логику статусов.

## Пример: сквозной сценарий через curl

```bash
BASE=http://localhost:8080
TOKEN=$(curl -s $BASE/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"anna@demo.ru","password":"demo2026"}' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

APP=$(curl -s $BASE/api/applications -H "$AUTH" -H 'Content-Type: application/json' -H "Idempotency-Key: $(uuidgen)" \
  -d '{"product_code":"WORKING_CAPITAL","purpose":"PURCHASE_GOODS","amount":2000000,"term_months":12}' | jq .id)

curl -s -X POST $BASE/api/applications/$APP/submit -H "$AUTH" -H 'Content-Type: application/json' -d '{"consent":true}' | jq .status.code
sleep 10
curl -s $BASE/api/applications/$APP -H "$AUTH" | jq '{status: .status.code, offer: .decision.offer}'
curl -s -X POST $BASE/api/applications/$APP/accept -H "$AUTH" | jq .status.code
curl -s -X POST $BASE/api/applications/$APP/sign -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"confirm":true,"signer_name":"Смирнова А. С."}' | jq '{status: .status.code, disbursement: .agreement.disbursement}'
```

## Действия с уведомлениями

Ручной дозапрос: `POST /api/applications/{id}/resubmit` требует документ, которого не было в `missing_items[].document_ids_before_request`. Без него — 409, с ним — MANUAL_REVIEW. Наличие нового файла означает ответ клиента, а не подтверждение его содержания; это проверяет аналитик.

Все операции требуют JWT и доступны только владельцу уведомления.

| Метод | Путь | Результат |
|---|---|---|
| POST | `/api/notifications/{id}/read` | Пометить одно уведомление прочитанным |
| DELETE | `/api/notifications/{id}` | Удалить одно уведомление |

Чужой или отсутствующий ID возвращает 404. Актуальные схемы ответов — в `docs/api/openapi.json`; примеры запросов — в Postman, раздел «5. Уведомления».

## Контракты смоделированных интеграций (сервис `mocks`)

| Источник | Запрос | Ответ (сокращённо) |
|---|---|---|
| ЕГРЮЛ/ЕГРИП | `GET /egrul/{inn}` | `inn, ogrn, name, legal_form, status (ACTIVE/LIQUIDATED), registered_at, okved, okved_name, address, director`; `404`, если не найдена |
| ФНС «Прозрачный бизнес» | `GET /fns/transparent-business/{inn}` | `mass_address, tax_arrears, disqualified_director, employees_count, tax_regime, founders[]` |
| БКИ | `GET /bki/report/{inn}` | `has_history, current_overdue_days, max_overdue_days_12m, total_monthly_payments, obligations[], inquiries_30d`; без истории — `has_history=false` |

Переменные `MOCK_FAILURE_RATE` и `MOCK_LATENCY_MS` позволяют имитировать нестабильность источников и проверить ретраи.
