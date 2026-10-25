import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorBox, Loading, StatusChip, TurnoverBars } from "../components/ui";
import { api } from "../lib/api";
import { age, compactMoney, date, money, months } from "../lib/format";
import { useResource } from "../lib/hooks";

const ACTIVE = new Set(["SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING", "MANUAL_REVIEW"]);

export default function Dashboard() {
  const apps = useResource(api.applications, [], (d) => (d?.some((a) => ACTIVE.has(a.status)) ? 3000 : null));
  const company = useResource(api.company, []);
  const fin = useResource(api.bankFinancials, []);

  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil((apps.data?.length ?? 0) / 8));
  const currentPage = Math.min(page, pageCount);
  const visibleApps = apps.data?.slice((currentPage - 1) * 8, currentPage * 8);

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
              </div>
            )}
            <div className="app-list">
              {visibleApps?.map((a) => (
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
            {pageCount > 1 && <nav className="pagination" aria-label="Страницы заявок">
              <button type="button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)} aria-label="Предыдущая страница">←</button>
              <span>Страница {currentPage} из {pageCount}</span>
              <button type="button" disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)} aria-label="Следующая страница">→</button>
            </nav>}
          </section>
          <Link to="/new" className="create-application"><span aria-hidden="true">＋</span> Создать заявку</Link>
        </div>

        <aside>
          <section className="panel">
            <div className="panel-title"><h3>Компания</h3><span className="muted small">из ЕГРЮЛ/ЕГРИП</span></div>
            {company.data ? (
              <dl className="company-details">
                <dt>ИНН</dt><dd className="num">{company.data.inn}</dd>
                <dt>ОГРН</dt><dd className="num">{company.data.ogrn ?? "—"}</dd>
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
              !fin.loading && <p className="small muted">История оборотов сейчас недоступна. Для заявки загрузите CSV-выписку: минимум 3 последовательных месяца, лучше 6; последний месяц — не старше 2 месяцев.</p>
            )}
          </section>
        </aside>
      </div>
    </>
  );
}
