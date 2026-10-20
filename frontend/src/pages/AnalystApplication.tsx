import { Fragment, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorBox, Loading, Route, StatusChip, TurnoverBars } from "../components/ui";
import { api, download, type AnalystApplication as AA } from "../lib/api";
import { age, dateTime, money, months, pct } from "../lib/format";
import { useAction, useResource } from "../lib/hooks";

const LIVE = new Set(["SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING"]);
const SOURCE_NAME: Record<string, string> = { EGRUL: "ЕГРЮЛ/ЕГРИП", FNS: "ФНС, «Прозрачный бизнес»", BKI: "Бюро кредитных историй" };
const LIMIT_NAME: Record<string, string> = {
  product_max: "Максимум продукта", revenue: "Доля годовой выручки", turnover: "Доля месячного оборота",
  dti: "Долговая нагрузка (DTI)", collateral: "90% стоимости залога",
};

export default function AnalystApplication() {
  const id = Number(useParams().id);
  const res = useResource(() => api.analystApplication(id), [id], (a) => (a && LIVE.has(a.status.code) ? 1500 : null));
  const [tab, setTab] = useState<"score" | "checks" | "audit">("score");
  const app = res.data;

  if (res.error && !app) return <ErrorBox error={res.error} onRetry={res.reload} />;
  if (!app) return <Loading />;

  return (
    <>
      <Link to="/analyst" className="back">← Очередь заявок</Link>
      <div className="page-head">
        <div>
          <div className="row gap-8 wrap">
            <h1>{app.company.name}</h1>
            <StatusChip code={app.status.code} title={app.status.title} />
          </div>
          <p>{app.number}: {app.product.name}, {money(app.amount)} на {months(app.term_months)}. Заявитель — {app.applicant.full_name}, {app.applicant.position?.toLowerCase()}.</p>
        </div>
      </div>

      <div className="grid-analyst">
        <div>
          <section className="panel">
            <div className="tabs" role="tablist">
              <button className="tab" role="tab" aria-selected={tab === "score"} onClick={() => setTab("score")}>Скоринг и решение</button>
              <button className="tab" role="tab" aria-selected={tab === "checks"} onClick={() => setTab("checks")}>Проверки ({app.checks.length})</button>
              <button className="tab" role="tab" aria-selected={tab === "audit"} onClick={() => setTab("audit")}>Аудит ({app.events.length})</button>
            </div>
            {tab === "score" && <ScoreTab app={app} />}
            {tab === "checks" && <ChecksTab app={app} />}
            {tab === "audit" && <AuditTab app={app} />}
          </section>

          <section className="panel">
            <div className="panel-title"><h3>Компания</h3></div>
            <dl className="kv-list">
              <dt>ИНН / ОГРН</dt><dd className="num">{app.company.inn} / {app.company.ogrn}</dd>
              <dt>Возраст бизнеса</dt><dd>{age(app.company.business_age_months)}</dd>
              <dt>ОКВЭД</dt><dd>{app.company.okved} {app.company.okved_name}</dd>
              <dt>Адрес</dt><dd>{app.company.address}</dd>
              <dt>Руководитель</dt><dd>{app.company.director}</dd>
              <dt>Клиент банка</dt><dd>{app.company.is_bank_client ? "Да" : "Нет"}</dd>
            </dl>
          </section>

          {app.financials && app.financials.months_count > 0 && (
            <section className="panel">
              <div className="panel-title"><h3>Обороты</h3><span className="muted small">{app.financials.source === "BANK_ACCOUNT" ? "внутренние данные банка" : "распознано из выписки клиента"}</span></div>
              <TurnoverBars fin={app.financials} />
              <dl className="kv" style={{ marginTop: 16 }}>
                <div><dt>Среднемесячные поступления</dt><dd className="num">{money(app.financials.avg_monthly_inflow)}</dd></div>
                <div><dt>Оценка годовой выручки</dt><dd className="num">{money(app.financials.annual_revenue_estimate)}</dd></div>
                <div><dt>Коэф. вариации</dt><dd className="num">{app.financials.stability_cv ?? "—"}</dd></div>
              </dl>
            </section>
          )}

          {app.documents.length > 0 && (
            <section className="panel">
              <div className="panel-title"><h3>Документы клиента</h3></div>
              {app.documents.map((d) => (
                <div key={d.id} className="row" style={{ padding: "6px 0" }}>
                  <span className="grow">{d.filename} <span className="muted small">({d.kind})</span></span>
                  <button className="btn text small" onClick={() => download(`/api/analyst/applications/${app.id}/documents/${d.id}`, d.filename)}>Скачать</button>
                </div>
              ))}
            </section>
          )}
        </div>

        <aside className="sticky">
          {app.allowed_actions.length > 0 ? <DecisionForm app={app} onDone={res.setData} /> : (
            <section className="panel">
              <div className="panel-title"><h3>Маршрут</h3></div>
              <Route items={app.timeline} live={LIVE.has(app.status.code)} />
            </section>
          )}
        </aside>
      </div>
    </>
  );
}

function ScoreTab({ app }: { app: AA }) {
  const d = app.decision;
  const sd = app.score_details;
  return (
    <div className="stack gap-24">
      {sd ? (
        <div className="score-ring">
          <div className="score-num num">{sd.score}</div>
          <div className={`grade ${sd.grade}`}>{sd.grade}</div>
          <div className="small muted">балл из 100, базовое значение {sd.base}.<br />Модель: прозрачная балльная (points-v1)</div>
        </div>
      ) : (
        <div className="callout warn">Скоринг не рассчитан — заявка остановлена до этапа оценки.</div>
      )}
      {sd && (
        <div>
          {sd.stop_factors.map((s) => <div key={s.code} className="callout bad" style={{ marginBottom: 8 }}>Стоп-фактор: {s.client_text}</div>)}
          {sd.factors.map((f) => (
            <div className="factor" key={f.code}>
              <div><div>{f.name}</div><div className="muted small">{f.value}</div></div>
              <div className="factor-bar" aria-hidden>
                <span className={f.points >= 0 ? "pos" : "neg"} style={{ width: `${Math.min(Math.abs(f.points) / 30, 1) * 50}%` }} />
              </div>
              <div className={`pts ${f.points > 0 ? "pos" : f.points < 0 ? "neg" : ""}`}>{f.points > 0 ? `+${f.points}` : f.points}</div>
            </div>
          ))}
        </div>
      )}
      {d && (
        <div className="stack gap-8">
          <h3>Решение {d.decided_by === "ANALYST" ? "аналитика" : "конвейера"}</h3>
          {d.recommendation && <div className="callout info">{d.recommendation}</div>}
          {d.offer && <p>Предложение: {d.offer.product_name}, {money(d.offer.amount)} на {months(d.offer.term_months)} под {pct(d.offer.rate)}, платёж {money(d.offer.monthly_payment)}.</p>}
          {d.limits && Object.keys(d.limits).length > 0 && (
            <dl className="kv-list">
              {Object.entries(d.limits).map(([k, v]) => <Fragment key={k}><dt>{LIMIT_NAME[k] ?? k}</dt><dd className="num">{money(v)}</dd></Fragment>)}
            </dl>
          )}
          {d.rules_fired && <p className="small muted">Сработавшие правила: {d.rules_fired.join(", ")}</p>}
          {d.analyst_comment && <p className="small">Комментарий аналитика: {d.analyst_comment}</p>}
        </div>
      )}
    </div>
  );
}

function ChecksTab({ app }: { app: AA }) {
  if (!app.checks.length) return <p className="muted">Проверки ещё не проводились.</p>;
  return (
    <div>
      {app.checks.map((c) => (
        <div className="check-row" key={c.id}>
          <div><b>{SOURCE_NAME[c.source] ?? c.source}</b><div className="muted small">попытка {c.attempt}</div></div>
          <div>
            {c.status === "OK" ? <span className="chip good">Данные получены</span> : c.status === "NOT_FOUND" ? <span className="chip bad">Не найдено</span> : <span className="chip bad">Ошибка: {c.error}</span>}
            {c.response && (
              <details style={{ marginTop: 6 }}>
                <summary>Ответ источника</summary>
                <pre className="json">{JSON.stringify(c.response, null, 2)}</pre>
              </details>
            )}
          </div>
          <div className="muted small num">{c.duration_ms} мс</div>
        </div>
      ))}
    </div>
  );
}

function AuditTab({ app }: { app: AA }) {
  return (
    <ul className="audit">
      {[...app.events].reverse().map((e) => (
        <li key={e.id}>
          <span className="muted">{dateTime(e.created_at)}</span>
          <div>
            <b>{e.event_type === "STATUS_CHANGED" ? `${e.from_status ?? "—"} → ${e.to_status}` : e.event_type}</b>
            <span className="muted">, {e.actor_name ?? e.actor_type}</span>
            {e.reason && <div>{e.reason}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}

function DecisionForm({ app, onDone }: { app: AA; onDone: (a: AA) => void }) {
  const proposed = app.decision?.offer;
  const [action, setAction] = useState<"APPROVE" | "COUNTER_OFFER" | "REJECT" | "REQUEST_INFO">(proposed && proposed.amount < app.amount ? "COUNTER_OFFER" : "APPROVE");
  const [amount, setAmount] = useState(String(proposed?.amount ?? app.amount));
  const [term, setTerm] = useState(String(proposed?.term_months ?? app.term_months));
  const [rate, setRate] = useState(String(proposed?.rate ?? ""));
  const [comment, setComment] = useState("");
  const [items, setItems] = useState("");
  const act = useAction();

  useEffect(() => { act.setError(null); }, [action]); // eslint-disable-line react-hooks/exhaustive-deps

  const withTerms = action === "APPROVE" || action === "COUNTER_OFFER";
  const submit = () => act.run(async () => onDone(await api.decide(app.id, {
    action, version: app.version, comment,
    amount: withTerms ? Number(amount) : undefined,
    term_months: withTerms ? Number(term) : undefined,
    rate: withTerms && rate ? Number(rate) : undefined,
    requested_items: action === "REQUEST_INFO" ? items.split("\n").map((s) => s.trim()).filter(Boolean) : undefined,
  })));

  const labels = { APPROVE: "Одобрить", COUNTER_OFFER: "Контрпредложение", REJECT: "Отказать", REQUEST_INFO: "Запросить данные" };

  return (
    <section className="panel stack gap-16">
      <div className="panel-title" style={{ marginBottom: 0 }}><h3>Решение по заявке</h3></div>
      <div className="filters" role="radiogroup" aria-label="Тип решения">
        {(Object.keys(labels) as (keyof typeof labels)[]).map((k) => (
          <button key={k} className="filter" role="radio" aria-checked={action === k} aria-pressed={action === k} onClick={() => setAction(k)}>{labels[k]}</button>
        ))}
      </div>
      {withTerms && (
        <div className="stack gap-8">
          <div className="field"><label htmlFor="d-amount">Сумма, ₽</label><input id="d-amount" className="input num" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} /></div>
          <div className="row gap-8">
            <div className="field grow"><label htmlFor="d-term">Срок, мес.</label><input id="d-term" className="input num" type="number" value={term} onChange={(e) => setTerm(e.target.value)} /></div>
            <div className="field grow"><label htmlFor="d-rate">Ставка, %</label><input id="d-rate" className="input num" type="number" step="0.1" placeholder="по грейду" value={rate} onChange={(e) => setRate(e.target.value)} /></div>
          </div>
        </div>
      )}
      {action === "REQUEST_INFO" && (
        <div className="field"><label htmlFor="d-items">Что запросить у клиента (каждый пункт с новой строки)</label>
          <textarea id="d-items" className="textarea" value={items} onChange={(e) => setItems(e.target.value)} placeholder="Приложите действующие договоры с заказчиками" /></div>
      )}
      <div className="field">
        <label htmlFor="d-comment">Обоснование</label>
        <textarea id="d-comment" className="textarea" value={comment} onChange={(e) => setComment(e.target.value)}
          placeholder={action === "REJECT" ? "Причина отказа — клиент увидит этот текст" : "Попадёт в аудит и будет показано клиенту"} />
      </div>
      <ErrorBox error={act.error} />
      <button className={`btn ${action === "REJECT" ? "" : "primary"} block`} disabled={act.busy || comment.trim().length < 3} onClick={submit}>
        {labels[action]}
      </button>
    </section>
  );
}
