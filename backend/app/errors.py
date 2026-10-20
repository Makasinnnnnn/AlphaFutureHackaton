class DomainError(Exception):
    """Ошибка бизнес-логики с понятным пользователю текстом и HTTP-кодом."""

    def __init__(self, code: str, message: str, http_status: int = 400, details: object | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details


def not_found(what: str = "Объект") -> DomainError:
    return DomainError("NOT_FOUND", f"{what} не найден(а)", 404)


def conflict(message: str, details: object | None = None) -> DomainError:
    return DomainError("CONFLICT", message, 409, details)
