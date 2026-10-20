import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorBox, Loading, StatusChip } from "../components/ui";
import { api } from "../lib/api";
import { dateTime, money, months } from "../lib/format";
import { useResource } from "../lib/hooks";

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
  const statuses = FILTERS[filter].statuses;
  const list = useResource(() => api.queue(statuses, q), [filter, q], () => 4000);
  const stats = useResource(api.stats, [], () => 6000);
  const s = stats.data;
  const count = (st: string[]) => (st.length ? st.reduce((n, x) => n + (s?.by_status[x] ?? 0), 0) : s?.total ?? 0);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Очередь заявок</h1>
          <p>Заявки, которые конвейер не смог решить автоматически, попадают в «Ждут решения».</p>
        </div>
      </div>

      {s && (
        <div className="stats-row">
          <div className="panel stat"><b className="num">{s.in_review}</b><span>ждут решения аналитика</span></div>
          <div className="panel stat"><b className="num">{s.total}</b><span>заявок всего</span></div>
          <div className="panel stat"><b className="num">{s.approval_rate != null ? `${Math.round(s.approval_rate * 100)}%` : "—"}</b><span>положительных решений</span></div>
          <div className="panel stat"><b className="num">{s.avg_decision_seconds != null ? `${Math.round(s.avg_decision_seconds)} с` : "—"}</b><span>от отправки до решения, в среднем</span></div>
        </div>
      )}

      <section className="panel">
        <div className="row wrap" style={{ justifyContent: "space-between", marginBottom: 16 }}>
          <div className="filters" role="group" aria-label="Фильтр по статусу">
            {FILTERS.map((f, i) => (
              <button key={f.label} className="filter" aria-pressed={filter === i} onClick={() => setFilter(i)}>
                {f.label}<span className="count">{count(f.statuses)}</span>
              </button>
            ))}
          </div>
          <input className="input" style={{ maxWidth: 260 }} placeholder="Номер, ИНН или название" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Поиск" />
        </div>
        <ErrorBox error={list.error} onRetry={list.reload} />
        {list.loading && !list.data && <Loading />}
        {list.data?.length === 0 && <div className="empty"><h3>Здесь пусто</h3><p>Заявок с таким статусом нет.</p></div>}
        {!!list.data?.length && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Заявка</th><th>Клиент</th><th>Продукт</th><th className="right">Сумма</th><th className="right">Балл</th><th>Статус</th><th>Изменена</th></tr>
              </thead>
              <tbody>
                {list.data.map((a) => (
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
      </section>
    </>
  );
}
