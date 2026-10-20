.PHONY: up down reset logs test e2e openapi data

up:            ## Собрать и запустить всё
	docker compose up --build -d
	@echo "Интерфейс: http://localhost:8080   Swagger: http://localhost:8080/api/docs"

down:          ## Остановить
	docker compose down

reset:         ## Остановить и удалить данные
	docker compose down -v

logs:          ## Логи API и воркера
	docker compose logs -f api worker

test:          ## Автотесты бэкенда (нужен локальный PostgreSQL)
	cd backend && pytest

e2e:           ## Сквозная проверка работающей системы
	python scripts/e2e_check.py --base http://localhost:8080

openapi:       ## Обновить docs/api/openapi.json
	cd backend && python ../scripts/export_openapi.py

data:          ## Перегенерировать синтетические данные
	python scripts/generate_synthetic.py
