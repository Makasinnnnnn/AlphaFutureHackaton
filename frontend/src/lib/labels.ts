export const DOCUMENT_LABELS: Record<string, string> = {
  STATEMENT: "Выписка по счёту", EQUIPMENT_INVOICE: "Счёт на оборудование", OTHER: "Дополнительный документ",
};
export const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Черновик", SUBMITTED: "Заявка отправлена", VALIDATION: "Проверяем полноту данных",
  ENRICHMENT: "Проверяем компанию", SCORING: "Оцениваем заявку", NEED_INFO: "Нужны дополнительные данные",
  MANUAL_REVIEW: "Рассматривает специалист", APPROVED: "Кредит одобрен", COUNTER_OFFER: "Предложены другие условия",
  SIGNING: "Подписание договора", ISSUED: "Кредит выдан", REJECTED: "Отказ", CANCELLED: "Заявка отменена",
};
export const ACTOR_LABELS: Record<string, string> = { SYSTEM: "Система", CLIENT: "Клиент", ANALYST: "Аналитик" };
export const EVENT_LABELS: Record<string, string> = {
  UPDATED: "Данные заявки изменены", DOCUMENT_UPLOADED: "Документ загружен", PIPELINE_ERROR: "Ошибка обработки",
  STATUS_CHANGED: "Изменение статуса",
};
const MISSING_LABELS: Record<string, string> = { ...DOCUMENT_LABELS, EQUIPMENT_INFO: "Сведения об оборудовании", ANALYST_REQUEST: "Запрос специалиста" };
export function readableReason(value: string) {
  return value.replace(/\b(STATEMENT|EQUIPMENT_INVOICE|EQUIPMENT_INFO|ANALYST_REQUEST)\b/g, code => MISSING_LABELS[code]);
}
export function offerDiffers(app: { amount: number; term_months: number; product: { code: string } }, offer?: { amount: number; term_months: number; product_code: string } | null) {
  return !!offer && (offer.amount !== app.amount || offer.term_months !== app.term_months || offer.product_code !== app.product.code);
}
