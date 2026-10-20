const rub = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });

export const money = (v: number | null | undefined) => (v == null ? "—" : `${rub.format(v)} ₽`);

export const compactMoney = (v: number) => {
  if (v >= 1_000_000) return `${(v / 1_000_000).toLocaleString("ru-RU", { maximumFractionDigits: 2 })} млн ₽`;
  if (v >= 1_000) return `${(v / 1_000).toLocaleString("ru-RU", { maximumFractionDigits: 0 })} тыс. ₽`;
  return money(v);
};

export const pct = (v: number) => `${v.toLocaleString("ru-RU", { maximumFractionDigits: 2 })}%`;

export function months(n: number): string {
  const m10 = n % 10, m100 = n % 100;
  const w = m10 === 1 && m100 !== 11 ? "месяц" : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? "месяца" : "месяцев";
  return `${n} ${w}`;
}

export function age(monthsTotal: number | null): string {
  if (monthsTotal == null) return "—";
  const y = Math.floor(monthsTotal / 12), m = monthsTotal % 12;
  const yw = y % 10 === 1 && y % 100 !== 11 ? "год" : y % 10 >= 2 && y % 10 <= 4 && (y % 100 < 10 || y % 100 >= 20) ? "года" : "лет";
  if (y === 0) return months(m);
  return m ? `${y} ${yw} ${months(m)}` : `${y} ${yw}`;
}

export const dateTime = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

export const date = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" }) : "—";

const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
export const monthLabel = (ym: string) => {
  const [, m] = ym.split("-").map(Number);
  return MONTHS[m - 1];
};

export function annuity(amount: number, ratePct: number, term: number) {
  const r = ratePct / 100 / 12;
  if (!r) return amount / term;
  return (amount * r) / (1 - Math.pow(1 + r, -term));
}

export const uid = () =>
  (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`).replace(/-/g, "").slice(0, 32);

export type Tone = "neutral" | "progress" | "action" | "good" | "bad" | "muted";

export const STATUS_TONE: Record<string, Tone> = {
  DRAFT: "muted",
  SUBMITTED: "progress",
  VALIDATION: "progress",
  ENRICHMENT: "progress",
  SCORING: "progress",
  NEED_INFO: "action",
  MANUAL_REVIEW: "progress",
  APPROVED: "good",
  COUNTER_OFFER: "action",
  SIGNING: "action",
  ISSUED: "good",
  REJECTED: "bad",
  CANCELLED: "muted",
};
