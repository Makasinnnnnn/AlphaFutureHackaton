"""Статусная модель заявки (state machine).

Единственный источник истины о допустимых переходах. Любое изменение статуса
в системе проходит через `assert_transition` — недопустимый переход даёт 409.
"""
from enum import StrEnum


class Status(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VALIDATION = "VALIDATION"
    NEED_INFO = "NEED_INFO"
    ENRICHMENT = "ENRICHMENT"
    SCORING = "SCORING"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    APPROVED = "APPROVED"
    COUNTER_OFFER = "COUNTER_OFFER"
    REJECTED = "REJECTED"
    SIGNING = "SIGNING"
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"


class Actor(StrEnum):
    CLIENT = "CLIENT"
    ANALYST = "ANALYST"
    SYSTEM = "SYSTEM"


S = Status

# (из статуса, в статус) -> кто может выполнить переход
TRANSITIONS: dict[tuple[Status, Status], set[Actor]] = {
    (S.DRAFT, S.SUBMITTED): {Actor.CLIENT},
    (S.SUBMITTED, S.VALIDATION): {Actor.SYSTEM},
    (S.SUBMITTED, S.MANUAL_REVIEW): {Actor.SYSTEM},  # техническая ошибка после ограниченных повторов
    (S.VALIDATION, S.MANUAL_REVIEW): {Actor.SYSTEM},
    (S.VALIDATION, S.NEED_INFO): {Actor.SYSTEM},
    (S.VALIDATION, S.ENRICHMENT): {Actor.SYSTEM},
    (S.NEED_INFO, S.VALIDATION): {Actor.CLIENT},
    (S.NEED_INFO, S.MANUAL_REVIEW): {Actor.CLIENT},  # ответ на ручной запрос проверяет аналитик
    (S.ENRICHMENT, S.SCORING): {Actor.SYSTEM},
    (S.ENRICHMENT, S.REJECTED): {Actor.SYSTEM},  # стоп-фактор из реестров (ликвидация и т.п.)
    (S.ENRICHMENT, S.MANUAL_REVIEW): {Actor.SYSTEM},  # внешний источник недоступен после ретраев
    (S.SCORING, S.APPROVED): {Actor.SYSTEM},
    (S.SCORING, S.COUNTER_OFFER): {Actor.SYSTEM},
    (S.SCORING, S.MANUAL_REVIEW): {Actor.SYSTEM},
    (S.SCORING, S.REJECTED): {Actor.SYSTEM},
    (S.MANUAL_REVIEW, S.APPROVED): {Actor.ANALYST},
    (S.MANUAL_REVIEW, S.COUNTER_OFFER): {Actor.ANALYST},
    (S.MANUAL_REVIEW, S.REJECTED): {Actor.ANALYST},
    (S.MANUAL_REVIEW, S.NEED_INFO): {Actor.ANALYST},
    (S.APPROVED, S.SIGNING): {Actor.CLIENT},
    (S.COUNTER_OFFER, S.SIGNING): {Actor.CLIENT},
    (S.SIGNING, S.ISSUED): {Actor.CLIENT},
    # отмена клиентом до подписания
    (S.DRAFT, S.CANCELLED): {Actor.CLIENT},
    (S.SUBMITTED, S.CANCELLED): {Actor.CLIENT},
    (S.NEED_INFO, S.CANCELLED): {Actor.CLIENT},
    (S.APPROVED, S.CANCELLED): {Actor.CLIENT},
    (S.COUNTER_OFFER, S.CANCELLED): {Actor.CLIENT},
    (S.SIGNING, S.CANCELLED): {Actor.CLIENT},
}

TERMINAL = {S.ISSUED, S.REJECTED, S.CANCELLED}
PIPELINE = {S.SUBMITTED, S.VALIDATION, S.ENRICHMENT, S.SCORING}  # обрабатываются воркером
EDITABLE_BY_CLIENT = {S.DRAFT, S.NEED_INFO}


class TransitionError(Exception):
    def __init__(self, src: Status, dst: Status, actor: Actor):
        self.src, self.dst, self.actor = src, dst, actor
        super().__init__(f"Переход {src} → {dst} недоступен для {actor}")


def can_transition(src: Status, dst: Status, actor: Actor) -> bool:
    return actor in TRANSITIONS.get((src, dst), set())


def assert_transition(src: Status, dst: Status, actor: Actor) -> None:
    if not can_transition(src, dst, actor):
        raise TransitionError(src, dst, actor)


# Тексты для клиента: что происходит и что от него нужно (без банковского жаргона)
CLIENT_COPY: dict[Status, dict[str, str]] = {
    S.DRAFT: {
        "title": "Черновик",
        "what": "Заявка сохранена, но ещё не отправлена в банк.",
        "next": "Проверьте параметры и нажмите «Отправить заявку».",
    },
    S.SUBMITTED: {
        "title": "Заявка отправлена",
        "what": "Банк получил заявку и поставил её в очередь на обработку.",
        "next": "Ничего делать не нужно — статус обновится автоматически.",
    },
    S.VALIDATION: {
        "title": "Проверяем полноту данных",
        "what": "Убеждаемся, что для решения хватает информации и документов.",
        "next": "Ничего делать не нужно.",
    },
    S.NEED_INFO: {
        "title": "Нужна дополнительная информация",
        "what": "Для решения не хватает данных — список ниже.",
        "next": "Дополните заявку и нажмите «Отправить повторно».",
    },
    S.ENRICHMENT: {
        "title": "Проверяем компанию",
        "what": "Сверяем данные с государственными реестрами и бюро кредитных историй.",
        "next": "Обычно это занимает несколько секунд.",
    },
    S.SCORING: {
        "title": "Оцениваем заявку",
        "what": "Рассчитываем условия с учётом оборотов, кредитной истории и параметров заявки.",
        "next": "Решение появится здесь же.",
    },
    S.MANUAL_REVIEW: {
        "title": "Рассматривает специалист",
        "what": "Заявку внимательно изучает кредитный специалист — так бывает в нестандартных случаях.",
        "next": "Мы сообщим о решении в кабинете.",
    },
    S.APPROVED: {
        "title": "Одобрено",
        "what": "Банк готов выдать кредит на запрошенных условиях.",
        "next": "Проверьте условия и примите предложение.",
    },
    S.COUNTER_OFFER: {
        "title": "Есть предложение на других условиях",
        "what": "Запрошенные условия не подошли, но банк готов предложить альтернативу.",
        "next": "Сравните условия и примите или отклоните предложение.",
    },
    S.REJECTED: {
        "title": "Отказ",
        "what": "К сожалению, сейчас банк не может выдать кредит.",
        "next": "Посмотрите причины и рекомендации — по ним можно подать заявку позже.",
    },
    S.SIGNING: {
        "title": "Подписание договора",
        "what": "Договор сформирован и ждёт вашей подписи.",
        "next": "Ознакомьтесь с договором и подпишите его в кабинете.",
    },
    S.ISSUED: {
        "title": "Кредит выдан",
        "what": "Деньги зачислены на расчётный счёт компании.",
        "next": "График платежей доступен в карточке заявки.",
    },
    S.CANCELLED: {
        "title": "Заявка отменена",
        "what": "Заявка больше не обрабатывается.",
        "next": "Вы можете создать новую заявку в любой момент.",
    },
}

# Основной «счастливый» путь — для таймлайна в интерфейсе
HAPPY_PATH = [S.DRAFT, S.SUBMITTED, S.VALIDATION, S.ENRICHMENT, S.SCORING, S.APPROVED, S.SIGNING, S.ISSUED]
