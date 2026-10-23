import { Link } from "react-router-dom";
import { ErrorBox, Loading, StatusChip, TurnoverBars } from "../components/ui";
import { api } from "../lib/api";
import { age, compactMoney, date, money, months, registrationNumber } from "../lib/format";
import { useResource } from "../lib/hooks";

const ACTIVE = new Set(["SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING", "MANUAL_REVIEW"]);

export default function Dashboard() {
  const apps = useResource(api.applications, [], (d) => (d?.some((a) => ACTIVE.has(a.status)) ? 3000 : null));
  const company = useResource(api.company, []);
  const fin = useResource(api.bankFinancials, []);

  const needsAction = apps.data?.filter((a) => ["NEED_INFO", "APPROVED", "COUNTER_OFFER", "SIGNING", "DRAFT"].includes(a.status)) ?? [];

  return (
    <>
      <div className="page-head"><h1>Мои заявки</h1></div>

      <div className="grid-main">
        <div>
          {needsAction.length > 0 && (
            <div className="callout warn" style={{ marginBottom: 16 }}>
              {needsAction.length === 1 ? "Одна заявка ждёт вашего действия" : `Заявок, которые ждут вашего действия: ${needsAction.length}`}.
              {" "}<Link to={`/applications/${needsAction[0].id}`}>Открыть {needsAction[0].number}</Link>
            </div>
          )}
          <section className="panel">
            <div className="panel-title"><h2>Заявки</h2></div>
            <ErrorBox error={apps.error} onRetry={apps.reload} />
            {apps.loading && !apps.data && <Loading />}
            {apps.data && apps.data.length === 0 && (
              <div className="empty">
                <h3>Заявок пока нет</h3>
                <p>Расскажите, на что нужны деньги, — подберём подходящий кредит.</p>
                <Link to="/new" className="btn primary" style={{ marginTop: 16 }}>Подобрать кредит</Link>
              </div>
            )}
            <div className="app-list">
              {apps.data?.map((a) => (
                <Link key={a.id} to={`/applications/${a.id}`} className="app-row">
                  <div>
                    <div className="app-row-title">{a.product_name} на {compactMoney(a.amount)}</div>
                    <div className="muted small">{a.number}, {months(a.term_months)}, создана {date(a.created_at)}</div>
                  </div>
                  <div className="num">{money(a.amount)}</div>
                  <StatusChip code={a.status} title={a.status_title} />
                </Link>
              ))}
            </div>
          </section>
        </div>

        <aside>
          <section className="panel">
            <div className="panel-title"><h3>Компания</h3><span className="muted small">из ЕГРЮЛ/ЕГРИП</span></div>
            {company.data ? (
              <dl className="kv-list">
                <dt>ИНН</dt><dd className="num">{registrationNumber(company.data.inn)}</dd>
                <dt>ОГРН</dt><dd className="num">{registrationNumber(company.data.ogrn)}</dd>
                <dt>Работает</dt><dd>{age(company.data.business_age_months)}</dd>
                <dt>Вид деятельности</dt><dd>{company.data.okved} {company.data.okved_name}</dd>
                <dt>Руководитель</dt><dd>{company.data.director}</dd>
                <dt>Статус</dt><dd>{company.data.registry_status === "ACTIVE" ? "Действующая" : <span className="error-text">Ликвидирована</span>}</dd>
              </dl>
            ) : company.error ? <ErrorBox error={company.error} /> : <Loading />}
          </section>
          <section className="panel">
            <div className="panel-title"><h3>Обороты по счёту</h3></div>
            {fin.data ? (
              <>
                <p className="small muted">В среднем поступает</p>
                <div className="amount-l num">{money(fin.data.avg_monthly_inflow)}</div>
                <p className="small muted">в месяц</p>
                <TurnoverBars fin={fin.data} />
                <p className="source-tag" style={{ marginTop: 12 }}>Эти данные подставятся в заявку автоматически</p>
              </>
            ) : (
              !fin.loading && <p className="small muted">У компании нет счёта в банке. Для заявки понадобится выписка из вашего банка за 6 месяцев — кабинет распознает её сам.</p>
            )}
          </section>
        </aside>
      </div>
    </>
  );
}
