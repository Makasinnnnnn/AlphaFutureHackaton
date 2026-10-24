export type Role = "CLIENT" | "ANALYST";

export interface User {
  id: number;
  email: string;
  role: Role;
  full_name: string;
  position?: string | null;
  company_inn?: string | null;
}

export interface DemoAccount {
  email: string;
  password: string;
  role: Role;
  full_name: string;
  company_name: string | null;
  scenario: string;
}

export interface Company {
  inn: string;
  name: string;
  legal_form: string;
  ogrn: string | null;
  okved: string | null;
  okved_name: string | null;
  address: string | null;
  director: string | null;
  registered_at: string | null;
  registry_status: string | null;
  is_bank_client: boolean;
  business_age_months: number | null;
}

export interface MonthRow { month: string; inflow: number; outflow: number }

export interface Financials {
  source: "BANK_ACCOUNT" | "STATEMENT_UPLOAD" | null;
  source_label: string | null;
  months: MonthRow[];
  months_count: number;
  avg_monthly_inflow: number | null;
  annual_revenue_estimate: number | null;
  stability_cv: number | null;
  period_from: string | null;
  period_to: string | null;
}

export interface Product {
  code: string;
  name: string;
  short_description: string;
  purposes: string[];
  min_amount: number;
  max_amount: number;
  min_term_months: number;
  max_term_months: number;
  base_rate: number;
  requires_collateral: boolean;
  min_business_age_months: number;
}

export interface Purpose { code: string; title: string; hint: string; products: string[] }

export interface Recommendation { product: Product; why: string; rank: number; estimated_rate_from: number }
export interface RecommendResult {
  purpose: string | null;
  purpose_title: string | null;
  engine: "rules" | "llm";
  recommendations: Recommendation[];
  note: string | null;
}

export interface Offer {
  product_code: string;
  product_name: string;
  amount: number;
  term_months: number;
  rate: number;
  monthly_payment: number;
}

export interface Reason { impact: "positive" | "negative" | "neutral"; text: string }

export interface Decision {
  outcome: string;
  requested_terms?: { rate: number; monthly_payment: number; is_overdraft: boolean };
  offer: Offer | null;
  reasons: Reason[];
  decided_by?: string;
  decided_at?: string;
  analyst_comment?: string | null;
  recommendation?: string | null;
  limits?: Record<string, number>;
  rules_fired?: string[];
  system_decision?: { outcome?: string; offer?: Offer | null; recommendation?: string | null };
}

export interface TimelineItem {
  status: string;
  title: string;
  at: string | null;
  state: "done" | "current" | "upcoming" | "skipped";
  actor: string | null;
  reason: string | null;
}

export interface DocumentInfo {
  id: number;
  kind: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  parsed: { rows: number; months: MonthRow[]; warnings: string[] } | null;
  created_at: string;
}

export interface ScheduleRow { n: number; date: string; payment: number; principal: number; interest: number; balance: number }

export interface Agreement {
  number: string;
  product_name: string;
  amount: number;
  term_months: number;
  rate: number;
  monthly_payment: number;
  total_payments: number | null;
  overpayment: number | null;
  schedule: ScheduleRow[];
  borrower: { name: string; inn: string; ogrn: string | null; director: string | null };
  created_at: string;
  signed_at: string | null;
  signer?: { name: string };
  signature?: { type: string; document_hash: string };
  disbursement?: { status: string; amount: number; account: string; at: string };
}

export interface Application {
  id: number;
  number: string;
  version: number;
  status: { code: string; title: string; what: string; next: string };
  product: Product;
  purpose: string | null;
  purpose_title: string | null;
  purpose_comment: string | null;
  amount: number;
  term_months: number;
  estimated_monthly_payment: number | null;
  collateral: { equipment_name?: string; equipment_cost?: number; supplier?: string } | null;
  financials: Financials | null;
  missing_items: { code: string; text: string; document_ids_before_request?: number[] }[] | null;
  analyst_comment: string | null;
  decision: Decision | null;
  agreement: Agreement | null;
  timeline: TimelineItem[];
  documents: DocumentInfo[];
  allowed_actions: string[];
  company: Company;
  created_at: string;
  submitted_at: string | null;
  status_changed_at: string;
  processing: boolean;
}

export interface ListItem {
  id: number;
  number: string;
  status: string;
  status_title: string;
  product_code: string;
  product_name: string;
  amount: number;
  term_months: number;
  company_inn: string;
  company_name: string;
  score: number | null;
  score_grade: string | null;
  created_at: string;
  status_changed_at: string;
  submitted_at: string | null;
}

export interface ScoreFactor { code: string; name: string; value: string; points: number; client_text: string; impact: string }

export interface AnalystApplication extends Application {
  score: number | null;
  score_grade: string | null;
  score_details: { base: number; score: number; grade: string; factors: ScoreFactor[]; stop_factors: { code: string; client_text: string }[] } | null;
  checks: { id: number; source: string; status: string; attempt: number; duration_ms: number | null; response: Record<string, unknown> | null; error: string | null; created_at: string }[];
  events: { id: number; event_type: string; from_status: string | null; to_status: string | null; actor_type: string; actor_name: string | null; reason: string | null; payload: Record<string, unknown> | null; created_at: string }[];
  applicant: User;
}

export interface Notification { id: number; application_id: number | null; title: string; body: string; is_read: boolean; created_at: string }
export interface Stats { by_status: Record<string, number>; total: number; in_review: number; approval_rate: number | null; avg_decision_seconds: number | null }

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

const TOKEN_KEY = "cc_token";

export const session = {
  get token(): string | null {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch { return memToken; }
  },
  set token(v: string | null) {
    memToken = v;
    try { v ? sessionStorage.setItem(TOKEN_KEY, v) : sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
  },
};
let memToken: string | null = null;

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

export async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = session.token;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers, body });
  } catch {
    throw new ApiError(0, "NETWORK", "Нет связи с сервером. Проверьте подключение и повторите.");
  }
  if (res.status === 401 && token && token === session.token) onUnauthorized();
  if (!res.ok) {
    let data: { error?: string; message?: string; details?: unknown } = {};
    try { data = await res.json(); } catch { /* not json */ }
    throw new ApiError(res.status, data.error ?? "HTTP_ERROR", data.message ?? `Ошибка ${res.status}`, data.details);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/api/auth/login", { method: "POST", json: { email, password } }),
  me: () => request<User>("/api/auth/me"),
  demoAccounts: () => request<DemoAccount[]>("/api/auth/demo-accounts"),
  company: () => request<Company>("/api/companies/me"),
  bankFinancials: () => request<Financials | null>("/api/companies/me/financials"),
  products: () => request<Product[]>("/api/products"),
  purposes: () => request<Purpose[]>("/api/products/purposes"),
  recommend: (body: { text?: string; purpose?: string }) =>
    request<RecommendResult>("/api/assistant/recommend", { method: "POST", json: body }),
  applications: () => request<ListItem[]>("/api/applications"),
  application: (id: number) => request<Application>(`/api/applications/${id}`),
  create: (body: unknown, key: string) =>
    request<Application>("/api/applications", { method: "POST", json: body, headers: { "Idempotency-Key": key } }),
  update: (id: number, body: unknown) => request<Application>(`/api/applications/${id}`, { method: "PATCH", json: body }),
  submit: (id: number) => request<Application>(`/api/applications/${id}/submit`, { method: "POST", json: { consent: true } }),
  resubmit: (id: number) => request<Application>(`/api/applications/${id}/resubmit`, { method: "POST" }),
  cancel: (id: number, reason?: string) =>
    request<Application>(`/api/applications/${id}/cancel`, { method: "POST", json: { reason } }),
  accept: (id: number) => request<Application>(`/api/applications/${id}/accept`, { method: "POST" }),
  sign: (id: number, signer_name: string) =>
    request<Application>(`/api/applications/${id}/sign`, { method: "POST", json: { confirm: true, signer_name } }),
  upload: (id: number, kind: string, file: File) => {
    const fd = new FormData();
    fd.append("kind", kind);
    fd.append("file", file);
    return request<Application>(`/api/applications/${id}/documents`, { method: "POST", body: fd });
  },
  notifications: () => request<{ unread: number; items: Notification[] }>("/api/notifications"),
  deleteNotification: (id: number) => request<void>(`/api/notifications/${id}`, { method: "DELETE" }),
  readNotification: (id: number) => request<void>(`/api/notifications/${id}/read`, { method: "POST" }),
  readAll: () => request<void>("/api/notifications/read-all", { method: "POST" }),
  queue: (statuses: string[], q: string) => {
    const p = new URLSearchParams();
    statuses.forEach((s) => p.append("status", s));
    if (q) p.set("q", q);
    return request<ListItem[]>(`/api/analyst/applications?${p}`);
  },
  analystApplication: (id: number) => request<AnalystApplication>(`/api/analyst/applications/${id}`),
  decide: (id: number, body: unknown) =>
    request<AnalystApplication>(`/api/analyst/applications/${id}/decision`, { method: "POST", json: body }),
  stats: () => request<Stats>("/api/analyst/stats"),
};

export async function download(path: string, filename: string) {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${session.token}` } });
  if (!res.ok) throw new ApiError(res.status, "DOWNLOAD", "Не удалось скачать файл");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
