import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorBox, Loading, StatusChip } from "../components/ui";
import { api } from "../lib/api";
import { dateTime, money, months } from "../lib/format";
import { useResource } from "../lib/hooks";
import { BackToTop } from "../components/BackToTop";

const FILTERS: { label: string; statuses: string[] }[] = [
  { label: "Ждут решения", statuses: ["MANUAL_REVIEW"] },
  { label: "В конвейере", statuses: ["SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING"] },
  { label: "Дозапрос у клиента", statuses: ["NEED_INFO"] },
  { label: "Одобрены", statuses: ["APPROVED", "COUNTER_OFFER", "SIGNING", "ISSUED"] },
  { label: "Отказы", statuses: ["REJECTED"] },
  { label: "Все", statuses: [] },
];

export default function AnalystQueue() {
  const nav = useNavigate();
  const [filter, setFilter] = useState(0);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [refreshing, setRefreshing] = useState(false);
  const statuses = FILTERS[filter].statuses;
  const list = useResource(() => api.queuePage(statuses, q, pageSize, page * pageSize), [filter, q, page, pageSize], () => 4000);
  const stats = useResource(api.stats, [], () => 6000);
  const s = stats.data;
  const total = list.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const rows = list.data?.items;
  useEffect(() => {
    if (list.data && page >= pages) setPage(pages - 1);
  }, [list.data, page, pages]);
  const chooseFilter = (index: number) => { setFilter(index); setPage(0); };
  const refresh = async () => {
    setRefreshing(true);
    try { await Promise.all([list.reload(), stats.reload()]); }
    finally { setRefreshing(false); }
  };
  const changePage = (next: number) => {
    setPage(next);
    window.scrollTo({ top: 0, behavior: "auto" });
  };
  const count = (st: string[]) => (st.length ? st.reduce((n, x) => n + (s?.by_status[x] ?? 0), 0) : s?.total ?? 0);

  return (
    <div className="analyst-queue">
      <div className="page-head">
        <div>
          <h1>Очередь заявок</h1>
          <p>Заявки, которые конвейер не смог решить автоматически, попадают в «Ждут решения».</p>
        </div>
        <button type="button" className="btn ghost" disabled={refreshing} onClick={refresh}>{refreshing ? "Обновляем…" : "↻ Обновить"}</button>
      </div>

      <ErrorBox error={stats.error} onRetry={stats.reload} />
      {s && (
        <div className="stats-row">
          <button type="button" className="panel stat stat-link" aria-pressed={filter === 0} onClick={() => chooseFilter(0)}><b className="num">{s.in_review}</b><span>ждут решения аналитика ↗</span></button>
          <button type="button" className="panel stat stat-link" aria-pressed={filter === 5} onClick={() => chooseFilter(5)}><b className="num">{s.total}</b><span>заявок всего ↗</span></button>
          <button type="button" className="panel stat stat-link" aria-pressed={filter === 3} onClick={() => chooseFilter(3)}><b className="num">{s.approval_rate != null ? `${Math.round(s.approval_rate * 100)}%` : "—"}</b><span>положительных решений ↗</span></button>
          <div className="panel stat"><b className="num">{s.avg_decision_seconds != null ? `${Math.round(s.avg_decision_seconds)} с` : "—"}</b><span>до решения или передачи аналитику, в среднем</span></div>
        </div>
      )}

      <section className="panel">
        <div className="row wrap" style={{ justifyContent: "space-between", marginBottom: 16 }}>
          <div className="filters" role="group" aria-label="Фильтр по статусу">
            {FILTERS.map((f, i) => (
              <button key={f.label} className="filter" aria-pressed={filter === i} onClick={() => chooseFilter(i)}>
                {f.label}<span className="count">{count(f.statuses)}</span>
              </button>
            ))}
          </div>
          <input className="input" style={{ maxWidth: 260 }} placeholder="Номер, ИНН или название" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} aria-label="Поиск" />
        </div>
        <div className="queue-pagination">
          <label className="row gap-8">На странице
            <select className="input" aria-label="Заявок на странице" value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}>
              {[10, 20, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
          <span aria-live="polite">{list.data ? total ? `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, total)} из ${total}` : "0 заявок" : "Загружаем…"}</span>
        </div>
        <ErrorBox error={list.error} onRetry={list.reload} />
        {list.loading && !list.data && <Loading />}
        {rows?.length === 0 && <div className="empty"><h3>Здесь пусто</h3><p>Заявок с таким статусом и поисковым запросом нет.</p></div>}
        {!!rows?.length && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Заявка</th><th>Клиент</th><th>Продукт</th><th className="right">Сумма</th><th className="right">Балл</th><th>Статус</th><th>Изменена</th></tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} className="clickable" tabIndex={0} onClick={() => nav(`/analyst/applications/${a.id}`)}
                    onKeyDown={(e) => e.key === "Enter" && nav(`/analyst/applications/${a.id}`)}>
                    <td className="num">{a.number}</td>
                    <td><div>{a.company_name}</div><div className="muted small num">ИНН {a.company_inn}</div></td>
                    <td>{a.product_name}<div className="muted small">{months(a.term_months)}</div></td>
                    <td className="right num">{money(a.amount)}</td>
                    <td className="right num">{a.score != null ? <b>{a.score} <span className="muted">{a.score_grade}</span></b> : "—"}</td>
                    <td><StatusChip code={a.status} title={a.status_title} /></td>
                    <td className="muted small">{dateTime(a.status_changed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {list.data && total > 0 && <nav className="queue-pagination" aria-label="Страницы очереди">
          <button type="button" className="btn ghost" disabled={page === 0 || list.loading} onClick={() => changePage(page - 1)}>← Назад</button>
          <span>Страница {page + 1} из {pages}</span>
          <button type="button" className="btn ghost" disabled={page + 1 >= pages || list.loading} onClick={() => changePage(page + 1)}>Далее →</button>
        </nav>}
      </section>
      <BackToTop />
    </div>
  );
}
