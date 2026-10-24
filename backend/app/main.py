import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError

from app.api.routes import api, health
from app.config import get_settings
from app.domain.statuses import CLIENT_COPY, TransitionError
from app.errors import DomainError
from app.logging_conf import request_id_var, setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("api")

app = FastAPI(
    title="Умный кредитный кабинет предпринимателя — API",
    version="1.0.0",
    description=(
        "Цифровой кредитный конвейер для малого и микробизнеса: подбор продукта, заявка, "
        "проверки (моки ЕГРЮЛ/ФНС/БКИ), скоринг, кредитное решение, подписание (симуляция).\n\n"
        "Авторизация: `POST /api/auth/login` → Bearer-токен. Тестовые учётки: `GET /api/auth/demo-accounts`."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    token = request_id_var.set(rid)
    started = time.monotonic()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if not request.url.path.startswith("/health"):
        log.info("request", extra={"ctx": {
            "request_id": rid, "method": request.method, "path": request.url.path,
            "status": response.status_code, "ms": int((time.monotonic() - started) * 1000),
        }})
    return response


def _err(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={
        "error": code, "message": message, "details": details, "request_id": request_id_var.get(),
    })


@app.exception_handler(DomainError)
async def domain_error(_: Request, exc: DomainError):
    return _err(exc.http_status, exc.code, exc.message, exc.details)


@app.exception_handler(TransitionError)
async def transition_error(_: Request, exc: TransitionError):
    return _err(409, "INVALID_TRANSITION",
                f"Действие недоступно: заявка в статусе «{CLIENT_COPY[exc.src]['title']}».",
                {"from": exc.src, "to": exc.dst})


@app.exception_handler(StaleDataError)
async def stale(_: Request, exc: StaleDataError):
    return _err(409, "CONCURRENT_MODIFICATION", "Заявка была изменена параллельно — обновите страницу и повторите.")


@app.exception_handler(RequestValidationError)
async def validation(_: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return _err(422, "VALIDATION_ERROR", "Проверьте введённые данные", details)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error")
    return _err(500, "INTERNAL_ERROR", "Внутренняя ошибка. Мы уже разбираемся.")


app.include_router(health)
app.include_router(api)
