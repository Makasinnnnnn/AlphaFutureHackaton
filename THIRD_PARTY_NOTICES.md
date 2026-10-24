# THIRD_PARTY_NOTICES

Перечень сторонних компонентов, моделей, датасетов и сервисов, используемых в проверяемой версии решения, а также смоделированных интеграций.

Проверяемая версия **не зависит** от платных подписок, платных API, покупных данных и закрытых корпоративных лицензий. Инструменты, использованные только при разработке, в состав решения не входят.

## 1. Смоделированные интеграции

Реальные внешние сервисы недоступны по условиям кейса (автономность, синтетические данные). Они заменены локальным симулятором — сервис `mocks` (`mocks/app.py`). Контракты упрощены с сохранением смысла интеграции.

| Реальный источник | Что моделируется | Эндпоинт симулятора |
|---|---|---|
| ЕГРЮЛ / ЕГРИП (ФНС России) | Существование и статус субъекта, ОГРН, дата регистрации, ОКВЭД, адрес, руководитель | `GET /egrul/{inn}` |
| Сервис ФНС «Прозрачный бизнес» | Адрес массовой регистрации, налоговая задолженность, дисквалификация руководителя, учредители, численность, режим налогообложения | `GET /fns/transparent-business/{inn}` |
| Бюро кредитных историй | Наличие истории, обязательства, ежемесячные платежи, текущая и исторические просрочки, число запросов | `GET /bki/report/{inn}` |
| АБС банка (обороты по расчётному счёту) | Помесячные поступления и списания клиентов банка | таблица `account_turnovers`, заполняется из синтетических данных |
| Подписание документов (ПЭП/УКЭП) | Подтверждение в кабинете, SHA-256 условий договора | `POST /api/applications/{id}/sign` — без реальной подписи |
| Выдача денежных средств | Запись о зачислении на расчётный счёт | поле `agreement.disbursement`, статус `SIMULATED` |

## 2. Датасеты

| Датасет | Происхождение | Лицензия |
|---|---|---|
| `data/synthetic/companies.json` — 7 компаний, их данные реестров, ФНС, БКИ и обороты | Сгенерирован командой скриптом `scripts/generate_synthetic.py`. Все ИНН, ОГРН, ФИО, адреса и суммы вымышлены; совпадения случайны. | Собственный, распространяется вместе с решением |
| `test-data/*.csv` — выписки, `test-data/invoice_cnc_machine.pdf` — счёт | Сгенерированы командой | Собственный |

## 3. Модели

| Модель | Назначение | Лицензия | Статус |
|---|---|---|---|
| Qwen2.5-1.5B-Instruct (Alibaba Cloud), через Ollama | Классификация свободного описания задачи клиента для подбора продукта | Apache-2.0 (открытые веса) | **Опционально**, профиль `ai`, по умолчанию выключено. Основной сценарий работает без модели (правила по ключевым словам). |

Скоринг кредитного риска — собственная прозрачная балльная модель (`backend/app/domain/scoring.py`), без сторонних моделей.

## 4. Программные компоненты

### Backend и симулятор (Python 3.12)

| Пакет | Версия | Лицензия |
|---|---|---|
| fastapi | 0.151.0 | MIT |
| starlette | 1.9.0 | BSD-3-Clause |
| uvicorn (+ uvloop, httptools, watchfiles, websockets, h11) | 0.54.0 | BSD-3-Clause (uvloop, httptools, watchfiles — MIT) |
| pydantic, pydantic-core, pydantic-settings | 2.14.1 / 2.50.1 / 2.16.0 | MIT |
| sqlalchemy | 2.1.5 | MIT |
| alembic (+ mako, markupsafe) | 1.20.0 | MIT (markupsafe — BSD-3-Clause) |
| psycopg, psycopg-binary | 3.3.6 | LGPL-3.0-only (используется как динамически подключаемая библиотека без изменений) |
| httpx, httpcore | 0.28.1 / 1.0.9 | BSD-3-Clause |
| pyjwt | 2.15.1 | MIT |
| bcrypt | 5.0.0 | Apache-2.0 |
| python-multipart | 0.0.32 | Apache-2.0 |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| anyio, annotated-types, annotated-doc, typing-inspection | см. lock-файл | MIT |
| click, idna | 8.5.0 / 3.20 | BSD-3-Clause |
| certifi | 2026.10.19 | MPL-2.0 |
| typing-extensions | 4.16.0 | PSF-2.0 |
| pyyaml | 6.0.3 | MIT |
| opentelemetry-api (транзитивная) | 1.45.1 | Apache-2.0 |
| pytest (только тесты) | см. `requirements-dev.lock.txt` | MIT |

Точные версии и хеши — `backend/requirements.lock.txt`, `mocks/requirements.lock.txt`.

### Frontend

The Alfa-Bank mark uses the unchanged SVG path from `AlfaBankLogoMIcon`
in Alfa Laboratory's `@alfalab/icons-logotype` package (declared MIT):
https://github.com/alfa-laboratory/icons/blob/9ffde4b1d37abdacce63e45121a3fa9ce8d44b22/packages/logotype/src/AlfaBankLogoMIcon.tsx
The logo remains a trademark of its respective owner; usage in this hackathon
was explicitly authorized by the user. The upright notification bell and timeline checkmarks are simple project-owned SVG geometry.

Styrene UI font files can be obtained explicitly before building from the official bank CDN,
using URLs documented by Alfa Laboratory:
https://github.com/alfa-laboratory/core-components/blob/master/docs/6.typography.stories.mdx
Styrene is a proprietary typeface, not covered by the icons package's MIT license.
The user states hackathon permission to use the bank font. Font files are served
locally if supplied by the builder; this is not a general redistribution license. Styrene files are not included. The default bundled fonts are Onest and Unbounded.

| Пакет | Версия | Лицензия |
|---|---|---|
| react, react-dom, scheduler | 19.3.1 / 0.28.0 | MIT |
| react-router, react-router-dom (+ cookie, set-cookie-parser) | 7.18.4 | MIT |
| @fontsource/onest — шрифт Onest | 5.3.1 | SIL OFL 1.1 |
| @fontsource/unbounded — шрифт Unbounded | 5.3.0 | SIL OFL 1.1 |
| vite, @vitejs/plugin-react, typescript, @types/* (только сборка) | см. `package-lock.json` | MIT / Apache-2.0 |

Шрифты поставляются вместе с приложением, обращений к Google Fonts и другим CDN нет.

### Инфраструктура (Docker-образы)

| Образ | Лицензия |
|---|---|
| postgres:16.6-alpine | PostgreSQL License |
| python:3.12.8-slim | PSF License |
| node:22.12-alpine (только сборка) | MIT |
| nginx:1.27-alpine | BSD-2-Clause |
| ollama/ollama:0.5.4 (опционально) | MIT |

## 5. Внешние сервисы во время работы

По умолчанию нет. Решение работает автономно, без обращений за пределы `docker compose`. Опциональный OpenAI-совместимый адаптер обращается только к явно настроенному `LLM_BASE_URL`; для автономной сдачи это локальный сервер открытой модели. Внешний платный провайдер не требуется.
