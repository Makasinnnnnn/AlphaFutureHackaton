import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { DocumentsBlock } from "../components/Documents";
import { ErrorBox, Loading, Money, Route, StatusChip, TurnoverBars } from "../components/ui";
import { api, download, type Application } from "../lib/api";
import { date, dateTime, money, months, pct } from "../lib/format";
import { useAction, useResource } from "../lib/hooks";

const LIVE = new Set(["SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING"]);

export default function ApplicationPage() {
  const id = Number(useParams().id);
  const res = useResource(() => api.application(id), [id], (a) =>
    a && LIVE.has(a.status.code) ? 1200 : a?.status.code === "MANUAL_REVIEW" ? 4000 : null,
  );
  const app = res.data;

  if (res.error && !app) return <ErrorBox error={res.error} onRetry={res.reload} />;
  if (!app) return <Loading />;

  const set = (a: Application) => res.setData(a);
  const live = LIVE.has(app.status.code);

  return (
    <>
      <Link to="/" className="back">← Все заявки</Link>
      <div className="page-head">
        <div>
          <div className="row gap-8 wrap">
            <h1>{app.product.name}</h1>
            <StatusChip code={app.status.code} title={app.status.title} />
          </div>
          <p>Заявка {app.number}{app.submitted_at ? `, отправлена ${dateTime(app.submitted_at)}` : ""}</p>
        </div>
      </div>

      <div className="grid-app">
        <aside className="panel sticky">
          <div className="panel-title"><h3>Маршрут заявки</h3></div>
          <Route items={app.timeline} live={live} />
        </aside>

        <div>
          <StepPanel app={app} onChange={set} reload={res.reload} />
          <Details app={app} />
        </div>
      </div>
    </>
  );
}

function StepPanel({ app, onChange, reload }: { app: Application; onChange: (a: Application) => void; reload: () => void }) {
  const code = app.status.code;
  const act = useAction();
  const cancel = (label: string) => (
    <button className="btn danger" disabled={act.busy} onClick={() => {
      if (window.confirm(`${label}? Это действие нельзя отменить.`)) act.run(async () => onChange(await api.cancel(app.id)));
    }}>{label}</button>
  );

  if (LIVE.has(code) || code === "MANUAL_REVIEW") {
    return (
      <section className="panel" aria-live="polite">
        <h2>{app.status.title}</h2>
        <p className="muted" style={{ marginTop: 6 }}>{app.status.what}</p>
        <p style={{ marginTop: 14 }}>{app.status.next}</p>
        {code === "SUBMITTED" && <div style={{ marginTop: 16 }}>{cancel("Отозвать заявку")}</div>}
      </section>
    );
  }

  if (code === "DRAFT") return <DraftPanel app={app} onChange={onChange} />;
  if (code === "NEED_INFO") return <NeedInfoPanel app={app} onChange={onChange} />;

  if (code === "APPROVED" || code === "COUNTER_OFFER") {
    const offer = app.decision?.offer;
    if (!offer) return null;
    const counter = code === "COUNTER_OFFER";
    const productChanged = offer.product_code !== app.product.code;
    return (
      <section className="panel stack gap-16">
        <div>
          <h2>{counter ? "Банк предлагает другие условия" : "Кредит одобрен"}</h2>
          <p className="muted" style={{ marginTop: 4 }}>
            {counter ? "Запрошенные условия не подошли, но вот что банк готов выдать прямо сейчас." : "Условия совпадают с запрошенными. Осталось принять предложение и подписать договор."}
          </p>
        </div>
        {counter ? (
          <div className="compare">
            <div className="offer was">
              <div className="small">Вы запрашивали</div>
              <div className="amount-l num">{money(app.amount)}</div>
              <div className="small">{app.product.name}, {months(app.term_months)}</div>
            </div>
            <div className="offer accent">
              <div className="small muted">Предложение банка</div>
              <div className="amount-l num">{money(offer.amount)}</div>
              <div className="small">{productChanged ? <b>{offer.product_name}</b> : offer.product_name}, {offer.term_months !== app.term_months ? <b>{months(offer.term_months)}</b> : months(offer.term_months)}</div>
            </div>
          </div>
        ) : (
          <div className="offer accent">
            <Money value={offer.amount} size="xl" />
          </div>
        )}
        <dl className="kv">
          <div><dt>Ставка</dt><dd>{pct(offer.rate)} годовых</dd></div>
          <div><dt>Срок</dt><dd>{months(offer.term_months)}</dd></div>
          <div><dt>{offer.product_code === "OVERDRAFT" ? "Проценты в месяц при полном лимите" : "Платёж в месяц"}</dt><dd className="num">{money(offer.monthly_payment)}</dd></div>
        </dl>
        <Reasons app={app} />
        <ErrorBox error={act.error} />
        <div className="row wrap">
          <button className="btn primary" disabled={act.busy} onClick={() => act.run(async () => onChange(await api.accept(app.id)))}>
            Принять и перейти к договору
          </button>
          {cancel(counter ? "Отказаться от предложения" : "Отказаться")}
        </div>
      </section>
    );
  }

  if (code === "SIGNING") return <SigningPanel app={app} onChange={onChange} cancel={cancel("Отказаться от кредита")} />;

  if (code === "ISSUED" && app.agreement) {
    const ag = app.agreement;
    return (
      <section className="panel stack gap-16">
        <div className="callout good">Договор {ag.number} подписан {dateTime(ag.signed_at)}. Деньги зачислены на счёт {ag.disbursement?.account} (симуляция).</div>
        <Money value={ag.amount} size="xl" />
        <dl className="kv">
          <div><dt>Ставка</dt><dd>{pct(ag.rate)}</dd></div>
          <div><dt>Срок</dt><dd>{months(ag.term_months)}</dd></div>
          <div><dt>Платёж</dt><dd className="num">{money(ag.monthly_payment)}</dd></div>
          {ag.overpayment != null && <div><dt>Переплата за весь срок</dt><dd className="num">{money(ag.overpayment)}</dd></div>}
        </dl>
        {ag.schedule.length > 0 && <Schedule app={app} />}
      </section>
    );
  }

  if (code === "REJECTED") {
    return (
      <section className="panel stack gap-16">
        <h2>Сейчас банк не может выдать кредит</h2>
        <p className="muted">Ниже — что повлияло на решение. Когда ситуация изменится, можно подать новую заявку.</p>
        <Reasons app={app} open />
        <Link to="/new" className="btn ghost" style={{ alignSelf: "flex-start" }}>Подобрать другой вариант</Link>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>{app.status.title}</h2>
      <p className="muted" style={{ marginTop: 6 }}>{app.status.what} {app.status.next}</p>
      <button className="btn text" onClick={reload} style={{ marginTop: 8 }}>Обновить</button>
    </section>
  );
}

function Reasons({ app, open = false }: { app: Application; open?: boolean }) {
  const reasons = app.decision?.reasons ?? [];
  if (!reasons.length) return null;
  const list = (
    <ul className="reasons" style={{ marginTop: 10 }}>
      {reasons.map((r, i) => <li key={i} className={r.impact}>{r.text}</li>)}
    </ul>
  );
  if (open) return list;
  return (
    <details>
      <summary>Почему такое решение</summary>
      {list}
    </details>
  );
}

function DraftPanel({ app, onChange }: { app: Application; onChange: (a: Application) => void }) {
  const act = useAction();
  const [consent, setConsent] = useState(false);
  return (
    <section className="panel stack gap-16">
      <h2>Черновик не отправлен</h2>
      <p className="muted">{money(app.amount)} на {months(app.term_months)}. Проверьте документы и отправьте заявку в банк.</p>
      {(app.financials?.source !== "BANK_ACCOUNT" || app.product.requires_collateral) && (
        <DocumentsBlock app={app} onChange={onChange} needStatement={app.financials?.source !== "BANK_ACCOUNT"} />
      )}
      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>Даю согласие на обработку данных компании и запрос кредитной истории в бюро кредитных историй</span>
      </label>
      <ErrorBox error={act.error} />
      <div className="row wrap">
        <button className="btn primary" disabled={!consent || act.busy} onClick={() => act.run(async () => onChange(await api.submit(app.id)))}>Отправить заявку</button>
        <button className="btn danger" disabled={act.busy} onClick={() => act.run(async () => onChange(await api.cancel(app.id, "Черновик удалён")))}>Удалить черновик</button>
      </div>
    </section>
  );
}

function NeedInfoPanel({ app, onChange }: { app: Application; onChange: (a: Application) => void }) {
  const act = useAction();
  const items = app.missing_items ?? [];
  const codes = new Set(items.map((i) => i.code));
  const [eq, setEq] = useState({
    equipment_name: app.collateral?.equipment_name ?? "",
    equipment_cost: app.collateral?.equipment_cost ? String(app.collateral.equipment_cost) : "",
    supplier: app.collateral?.supplier ?? "",
  });
  const saveEq = () => act.run(async () => onChange(await api.update(app.id, {
    version: app.version,
    collateral: { equipment_name: eq.equipment_name, equipment_cost: Number(eq.equipment_cost) || null, supplier: eq.supplier || null },
  })));
  const eqSaved = !!(app.collateral?.equipment_name && app.collateral?.equipment_cost);
  const statementOk = (app.financials?.months_count ?? 0) >= 3;
  const invoiceOk = app.documents.some((d) => d.kind === "EQUIPMENT_INVOICE");
  const done = (!codes.has("STATEMENT") || statementOk) && (!codes.has("EQUIPMENT_INFO") || eqSaved) && (!codes.has("EQUIPMENT_INVOICE") || invoiceOk);

  return (
    <section className="panel stack gap-16">
      <div>
        <h2>Чтобы принять решение, нужно ещё немного данных</h2>
        {app.analyst_comment && <p className="muted" style={{ marginTop: 4 }}>Комментарий специалиста: {app.analyst_comment}</p>}
      </div>
      <ul className="reasons">
        {items.map((i) => <li key={i.code + i.text} className="negative">{i.text}</li>)}
      </ul>

      {codes.has("EQUIPMENT_INFO") && (
        <div className="stack gap-8">
          <div className="row wrap gap-16">
            <div className="field grow"><label htmlFor="n-eq">Оборудование</label>
              <input id="n-eq" className="input" value={eq.equipment_name} onChange={(e) => setEq({ ...eq, equipment_name: e.target.value })} /></div>
            <div className="field" style={{ width: 180 }}><label htmlFor="n-cost">Стоимость, ₽</label>
              <input id="n-cost" className="input num" type="number" value={eq.equipment_cost} onChange={(e) => setEq({ ...eq, equipment_cost: e.target.value })} /></div>
          </div>
          <div className="row">
            <button className="btn ghost small" onClick={saveEq} disabled={act.busy || !eq.equipment_name || !eq.equipment_cost}>Сохранить</button>
            {eqSaved && <span className="source-tag">Сохранено</span>}
          </div>
        </div>
      )}
      <DocumentsBlock app={app} onChange={onChange} needStatement={codes.has("STATEMENT")}
        only={codes.has("ANALYST_REQUEST") ? new Set(["STATEMENT", "EQUIPMENT_INVOICE", "OTHER"]) : undefined} />
      <ErrorBox error={act.error} />
      <div className="row wrap">
        <button className="btn primary" disabled={act.busy || !done} onClick={() => act.run(async () => onChange(await api.resubmit(app.id)))}>Отправить повторно</button>
        {!done && <span className="hint">Кнопка станет доступна, когда все пункты будут выполнены</span>}
      </div>
    </section>
  );
}

function SigningPanel({ app, onChange, cancel }: { app: Application; onChange: (a: Application) => void; cancel: ReactNode }) {
  const act = useAction();
  const ag = app.agreement!;
  const [agree, setAgree] = useState(false);
  const [signer, setSigner] = useState(ag.borrower.director ?? "");
  return (
    <section className="panel stack gap-16">
      <h2>Подпишите договор</h2>
      <div className="agreement">
        <b>Кредитный договор {ag.number}</b>
        <p className="small muted">Сформирован {date(ag.created_at)}</p>
        <h4>Стороны</h4>
        <p>Банк (кредитор) и {ag.borrower.name}, ИНН {ag.borrower.inn}{ag.borrower.ogrn ? `, ОГРН ${ag.borrower.ogrn}` : ""} (заёмщик).</p>
        <h4>Предмет</h4>
        <p>{ag.product_name}: {money(ag.amount)} на {months(ag.term_months)} под {pct(ag.rate)} годовых.</p>
        <h4>Погашение</h4>
        <p>{ag.schedule.length ? `Ежемесячными аннуитетными платежами по ${money(ag.monthly_payment)}. Полная сумма выплат — ${money(ag.total_payments)}.` : "Поступления на расчётный счёт автоматически гасят задолженность по овердрафту."}</p>
        <h4>Подписание</h4>
        <p>Договор подписывается простой электронной подписью в кабинете. В прототипе подпись и выдача средств моделируются, реальные операции не проводятся.</p>
      </div>
      {ag.schedule.length > 0 && <Schedule app={app} preview />}
      <div className="field" style={{ maxWidth: 420 }}>
        <label htmlFor="signer">Подписант</label>
        <input id="signer" className="input" value={signer} onChange={(e) => setSigner(e.target.value)} />
      </div>
      <label className="check">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
        <span>Ознакомлен с условиями договора и графиком платежей, подписываю договор от имени компании</span>
      </label>
      <ErrorBox error={act.error} />
      <div className="row wrap">
        <button className="btn primary" disabled={!agree || signer.trim().length < 3 || act.busy}
          onClick={() => act.run(async () => onChange(await api.sign(app.id, signer.trim())))}>Подписать и получить деньги</button>
        {cancel}
      </div>
    </section>
  );
}

function Schedule({ app, preview = false }: { app: Application; preview?: boolean }) {
  const rows = app.agreement?.schedule ?? [];
  const shown = preview ? rows.slice(0, 3) : rows;
  return (
    <details open={!preview}>
      <summary>График платежей ({rows.length} платежей)</summary>
      <div className="table-wrap">
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>№</th><th>Дата</th><th className="right">Платёж</th><th className="right">Основной долг</th><th className="right">Проценты</th><th className="right">Остаток</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.n}><td>{r.n}</td><td>{date(r.date)}</td><td className="right num">{money(r.payment)}</td><td className="right num">{money(r.principal)}</td><td className="right num">{money(r.interest)}</td><td className="right num">{money(r.balance)}</td></tr>
            ))}
          </tbody>
        </table>
        {preview && rows.length > 3 && <p className="hint" style={{ marginTop: 6 }}>…и ещё {rows.length - 3}. Полный график будет в карточке после подписания.</p>}
      </div>
    </details>
  );
}

function Details({ app }: { app: Application }) {
  return (
    <>
      <section className="panel">
        <div className="panel-title"><h3>Параметры заявки</h3></div>
        <dl className="kv">
          <div><dt>Цель</dt><dd>{app.purpose_title ?? "—"}</dd></div>
          <div><dt>Запрошено</dt><dd className="num">{money(app.amount)}</dd></div>
          <div><dt>Срок</dt><dd>{months(app.term_months)}</dd></div>
          {app.collateral?.equipment_name && <div><dt>Оборудование</dt><dd>{app.collateral.equipment_name}{app.collateral.equipment_cost ? `, ${money(app.collateral.equipment_cost)}` : ""}</dd></div>}
        </dl>
        {app.purpose_comment && <p className="small muted" style={{ marginTop: 12 }}>«{app.purpose_comment}»</p>}
      </section>
      {app.financials && app.financials.months_count > 0 && (
        <section className="panel">
          <div className="panel-title"><h3>Обороты</h3><span className="source-tag">{app.financials.source_label}</span></div>
          <TurnoverBars fin={app.financials} />
          <p className="small muted" style={{ marginTop: 10 }}>В среднем {money(app.financials.avg_monthly_inflow)} в месяц, оценка годовой выручки {money(app.financials.annual_revenue_estimate)}</p>
        </section>
      )}
      {app.documents.length > 0 && (
        <section className="panel">
          <div className="panel-title"><h3>Документы</h3></div>
          <div className="stack gap-8">
            {app.documents.map((d) => (
              <div key={d.id} className="row">
                <span className="grow">{d.filename}</span>
                <span className="muted small">{dateTime(d.created_at)}</span>
                <button className="btn text small" onClick={() => download(`/api/applications/${app.id}/documents/${d.id}`, d.filename)}>Скачать</button>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
