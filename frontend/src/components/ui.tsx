import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api, type ApiError, type Financials, type TimelineItem } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, monthLabel, money, STATUS_TONE } from "../lib/format";
import { useAction, useResource } from "../lib/hooks";

export function StatusChip({ code, title }: { code: string; title: string }) {
  return <span className={`chip ${STATUS_TONE[code] ?? "neutral"}`}>{title}</span>;
}

export function ErrorBox({ error, onRetry }: { error: ApiError | string | null; onRetry?: () => void }) {
  if (!error) return null;
  const msg = typeof error === "string" ? error : error.message;
  return (
    <div className="callout bad row" role="alert">
      <span className="grow">{msg}</span>
      {onRetry && <button className="btn small ghost" onClick={onRetry}>Повторить</button>}
    </div>
  );
}

export function Loading() {
  return <div className="skeleton" role="status"><span className="sr-only">Загружаем данные…</span></div>;
}

export function Brand() {
  return <><span className="route-mark" aria-hidden="true">А<span /></span><span className="brand-copy">Кредитный маршрут<small>кабинет предпринимателя</small></span></>;
}

function Bell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data, error, reload } = useResource(api.notifications, [], () => 5000);
  const markRead = useAction();
  const { user } = useAuth();

  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    const escape = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", escape); };
  }, []);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && data?.unread) await markRead.run(async () => { await api.readAll(); await reload(); });
  };
  const base = user?.role === "ANALYST" ? "/analyst/applications" : "/applications";

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="bell" onClick={toggle} aria-label={`Уведомления${data?.unread ? `, новых: ${data.unread}` : ""}`} aria-expanded={open}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>
        {!!data?.unread && <span className="dot">{data.unread}</span>}
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Уведомления">
          <div className="panel-title"><b>Уведомления</b><button className="btn text small" onClick={() => setOpen(false)} aria-label="Закрыть уведомления">Закрыть</button></div>
          <ErrorBox error={error || markRead.error} onRetry={reload} />
          {!data?.items.length && <p className="muted small" style={{ padding: 12 }}>Здесь появятся сообщения о движении ваших заявок.</p>}
          {data?.items.map((n) => (
            <Link key={n.id} to={n.application_id ? `${base}/${n.application_id}` : "#"} className={`note ${n.is_read ? "" : "unread"}`} onClick={() => setOpen(false)}>
              <b>{n.title}</b>
              <span>{n.body}</span>
              <div className="muted small">{dateTime(n.created_at)}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const isAnalyst = user?.role === "ANALYST";
  const home = isAnalyst ? "/analyst" : "/";
  const links = isAnalyst
    ? [{ to: "/analyst", label: "Очередь заявок", symbol: "▤" }, { to: "/help", label: "О прототипе", symbol: "?" }]
    : [{ to: "/", label: "Мои заявки", symbol: "▤" }, { to: "/new", label: "Новая заявка", symbol: "+" }, { to: "/help", label: "Помощь", symbol: "?" }];
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Перейти к содержимому</a>
      <aside className="app-sidebar">
        <Link to={home} className="brand"><Brand /></Link>
        <div className="sidebar-label">{isAnalyst ? "РАБОТА С ЗАЯВКАМИ" : "ФИНАНСИРОВАНИЕ БИЗНЕСА"}</div>
        <nav className="side-nav" aria-label="Разделы">
          {links.map((link) => <NavLink key={link.to} to={link.to} end><span aria-hidden="true">{link.symbol}</span>{link.label}</NavLink>)}
        </nav>
        <div className="sidebar-foot"><span className="demo-indicator" />Демонстрационный кабинет<p>Синтетические данные.<br />Реальные операции не проводятся.</p></div>
      </aside>
      <header className="topbar">
        <div className="topbar-inner">
          <Link className="mobile-brand brand" to={home}><Brand /></Link>
          <div className="workspace-name">{isAnalyst ? "Рабочее место аналитика" : "Кредитный кабинет"}<small>{isAnalyst ? "Решение с объяснением и историей" : "От заявки до графика платежей"}</small></div>
          <div className="spacer" />
          <Bell />
          <div className="who">
            {user?.full_name}
            <small>{user?.position}</small>
          </div>
          <button className="btn text" onClick={() => { logout(); nav("/login"); }}>Выйти</button>
        </div>
      </header>
      <nav className="mobile-nav" aria-label="Мобильная навигация">{links.map((link) => <NavLink key={link.to} to={link.to} end>{link.label}</NavLink>)}</nav>
      <main className="page" id="main-content" tabIndex={-1}>{children}<footer className="workspace-footer">Учебный прототип · Не является сервисом Альфа-Банка или предложением кредита</footer></main>
    </div>
  );
}

const FINAL_GOOD = new Set(["APPROVED", "ISSUED", "COUNTER_OFFER"]);
const FINAL_BAD = new Set(["REJECTED"]);

export function Route({ items, live }: { items: TimelineItem[]; live: boolean }) {
  let lastIdx = -1;
  items.forEach((t, i) => { if (t.state !== "upcoming") lastIdx = i; });
  return (
    <ol className="route" aria-label="Маршрут заявки">
      {items.map((t, i) => {
        const isCurrent = i === lastIdx;
        const state = isCurrent ? "current" : t.state;
        const tone = !isCurrent ? "" : FINAL_GOOD.has(t.status) ? "good" : FINAL_BAD.has(t.status) ? "bad" : t.status === "CANCELLED" ? "final" : "";
        return (
          <li key={`${t.status}-${i}`} className={`${state} ${tone} ${live && isCurrent ? "live" : ""}`} aria-current={isCurrent ? "step" : undefined}>
            <span className="node" aria-hidden />
            <div className="step-title">{t.title}</div>
            {t.at && <div className="step-meta">{dateTime(t.at)}{t.actor === "ANALYST" ? ", специалист банка" : ""}</div>}
            {t.reason && <div className="step-reason">{t.reason}</div>}
          </li>
        );
      })}
    </ol>
  );
}

export function TurnoverBars({ fin }: { fin: Financials }) {
  const max = Math.max(...fin.months.map((m) => m.inflow), 1);
  return (
    <div>
      <div className="bars" role="img" aria-label={`Поступления по месяцам, в среднем ${money(fin.avg_monthly_inflow)}`}>
        {fin.months.map((m) => (
          <div className="bar" key={m.month} title={`${m.month}: ${money(m.inflow)}`}>
            <span style={{ height: `${Math.max((m.inflow / max) * 100, 4)}%` }} />
            <small>{monthLabel(m.month)}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Money({ value, size = "l" }: { value: number | null | undefined; size?: "xl" | "l" }) {
  return <div className={`amount-${size} num`}>{money(value)}</div>;
}
