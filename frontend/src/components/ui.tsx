import { NotificationList, useNotifications } from "./Notifications";
import { BrandMark } from "./BrandMark";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { type ApiError, type Financials, type TimelineItem } from "../lib/api";
import { useAuth } from "../lib/auth";
import { compactMoney, dateTime, monthLabel, money, STATUS_TONE, turnoverScale } from "../lib/format";
import { scrollChartWithWheel } from "../lib/chartScroll";

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
  return <div className="skeleton" aria-label="Загрузка" />;
}

function Bell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data, error } = useNotifications();
  const { user } = useAuth();

  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const toggle = async () => {
    const next = !open;
    setOpen(next);

  };
  const notificationsPath = user?.role === "ANALYST" ? "/analyst/notifications" : "/notifications";

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="bell" onClick={toggle} aria-label={`Уведомления${data?.unread ? `, новых: ${data.unread}` : ""}`} aria-expanded={open}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4M12 2V1" /></svg>
        {!!data?.unread && <span className="dot">{data.unread}</span>}
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Уведомления">
          <div className="notifications-popover-head"><h3>Уведомления</h3><Link to={notificationsPath} onClick={() => setOpen(false)}>Все уведомления ↗</Link></div>
          {error && <p className="error-text" role="alert">Не удалось загрузить уведомления</p>}
          <NotificationList items={data?.items.slice(0, 5) ?? []} onOpen={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const isAnalyst = user?.role === "ANALYST";
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to={isAnalyst ? "/analyst" : "/"} className="brand">
            <BrandMark />
            <span>Кредитный кабинет<small>{isAnalyst ? "рабочее место аналитика" : "для бизнеса"}</small></span>
          </Link>
          <nav className="topnav" aria-label="Разделы">
            {isAnalyst ? (
              <NavLink to="/analyst" end>Очередь заявок</NavLink>
            ) : (
              <>
                <NavLink to="/" end>Мои заявки</NavLink>
                <NavLink to="/new">Получить финансирование</NavLink>
              </>
            )}
          </nav>
          <div className="spacer" />
          <Bell />
          <div className="who">
            {user?.full_name}
            <small>{user?.position}</small>
          </div>
          <button className="btn text" onClick={() => { logout(); nav("/login"); }}>Выйти</button>
        </div>
      </header>
      <main className="page">{children}</main>
    </>
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
            <span className="node" aria-hidden="true">{state === "done" && <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m3 8 3 3 7-7" /></svg>}</span>
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
  const viewport = useRef<HTMLDivElement>(null);
  const entries = [...fin.months].sort((a, b) => a.month.localeCompare(b.month));
  const { max, ticks } = turnoverScale(entries.map((m) => m.inflow));
  const [position, setPosition] = useState(0);
  const [scrollLimit, setScrollLimit] = useState(0);
  const latestShown = useRef<string | null>(null);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => scrollChartWithWheel(element, event);
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, []);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const measure = () => {
      const limit = Math.max(0, element.scrollWidth - element.clientWidth);
      setScrollLimit(limit);
      const latest = entries.at(-1)?.month ?? "";
      if (latestShown.current !== latest) {
        element.scrollLeft = limit;
        latestShown.current = latest;
      }
      setPosition(element.scrollLeft);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [fin.months]);
  const years = [...new Set(entries.map((m) => m.month.slice(0, 4)))].join(" – ");
  const move = (direction: number) => viewport.current?.scrollBy({ left: direction * 232, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  return (
    <div className="turnover">
      <div className="chart-top"><span className="hint">Поступления, ₽</span><div className="chart-controls">
        <button type="button" onClick={() => move(-1)} disabled={position <= 1} aria-label="Предыдущие месяцы">←</button>
        <button type="button" onClick={() => move(1)} disabled={position >= scrollLimit - 1} aria-label="Следующие месяцы">→</button>
      </div></div>
      <div className="chart-plot">
      <div className="chart-scale" aria-hidden="true">{ticks.map((value) => <span key={value} style={{ top: `${(1 - value / max) * 100}%` }}>{value === 0 ? "0" : compactMoney(value)}</span>)}</div>
      <div className="chart-scroll" ref={viewport} tabIndex={0} aria-label="Обороты по месяцам. Прокрутите для просмотра периода" onScroll={(e) => setPosition(e.currentTarget.scrollLeft)}>
        <div className="bars" style={{ width: entries.length * 116, minWidth: "100%" }}>
          <div className="chart-grid" aria-hidden="true">{ticks.map((value) => <i key={value} style={{ top: `${(1 - value / max) * 100}%` }} />)}</div>
          {entries.map((m) => <div className="bar" key={m.month}>
            <div className="bar-track" aria-label={`${monthLabel(m.month)} ${m.month.slice(0, 4)}: ${money(m.inflow)}`}><span style={{ height: `${Math.max(m.inflow / max * 100, 0)}%` }}><span className="bar-value">{compactMoney(m.inflow)}</span></span></div>
            <small>{monthLabel(m.month)}<span className="chart-month-year">{m.month.slice(0, 4)}</span></small>
          </div>)}
        </div>
      </div>
      </div>
      <div className="chart-footer"><span>{years || "Нет данных"}</span><span>{entries.length} мес. · прокрутите график</span></div>
    </div>
  );
}

export function Money({ value, size = "l" }: { value: number | null | undefined; size?: "xl" | "l" }) {
  return <div className={`amount-${size} num`}>{money(value)}</div>;
}
