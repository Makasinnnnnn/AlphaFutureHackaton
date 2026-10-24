# Версия и запуск для проверки

Источник: https://github.com/Makasinnnnnn/AlphaFutureHackaton . При сдаче указывайте **полный SHA проверенного коммита**, а не только меняющееся имя ветки. SHA отображается у коммита на GitHub и командой `git rev-parse HEAD`. Официальный Q&A допускает commit, tag или другой однозначный идентификатор; конкретное имя тега не обязательно.

```sh
git clone https://github.com/Makasinnnnnn/AlphaFutureHackaton.git
cd AlphaFutureHackaton
# Заменить значение ниже полным SHA из формы сдачи:
git checkout --detach <SUBMITTED_COMMIT_SHA>
docker compose up --build
```

Открыть http://localhost:8080, Swagger http://localhost:8080/api/docs . Все демопароли — `demo2026`; учётки перечислены в README и на странице входа. Запуск не требует платных API, GPU или модели: LLM выключена по умолчанию. Mocks и синтетические данные включены. Образы и зависимости загружаются при первой сборке, работающий основной сценарий внешних API не требует.

Минимальная приёмка: все пять сервисов `healthy`; сценарии [DEMO.md](team/DEMO.md) проходят; HTTP E2E завершается успешно. GitHub Actions отдельно проверяет чистую сборку и запуск Compose. Проверяйте зелёные jobs именно у выбранного SHA.

`docker compose down` останавливает сервисы с сохранением данных. `docker compose down -v` удаляет демоданные — использовать только для намеренного сброса.

## Комплект

- Продукт: [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md), границы и гипотезы: [product.md](product.md).
- Запуск, учётки, зависимости: корневой README, lock-файлы и Dockerfiles.
- Архитектура, API, состояния и данные: ссылки в README; `docs/api/openapi.json` и Postman-коллекция.
- Проверки: [test-scenarios.md](test-scenarios.md), [FULL_DEBUG.md](team/FULL_DEBUG.md), CI выбранного коммита.
- Лицензии и симуляторы: корневой `THIRD_PARTY_NOTICES.md`.

Репозиторий должен быть доступен проверяющим. Видео/презентация могут дополнить, но не заменить запускаемый код. Отправка в форму конкурса выполняется отдельно; публикация кода не означает отправленную заявку.

По объявлению организаторов — 26 октября до 18:00; часовой пояс в доступном экспорте не указан. Перед отправкой сверить время и поля на платформе. [Официальный Q&A](https://docs.google.com/document/d/1QsHdeEh1yGueUCawdg27ayetcjj0bv7QnJBEueQBy2o/edit).
