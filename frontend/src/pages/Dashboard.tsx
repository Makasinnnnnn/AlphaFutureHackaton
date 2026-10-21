import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorBox, Loading, StatusChip, TurnoverBars } from "../components/ui";
import { api } from "../lib/api";
import { age, date, money, months } from "../lib/format";
import { useResource } from "../lib/hooks";

const ACTIVE = new Set(["SUBMITTED", "VALIDATION", "ENRICHMENT", "SCORING", "MANUAL_REVIEW"]);
const ACTION = new Set(["NEED_INFO", "APPROVED", "COUNTER_OFFER", "SIGNING", "DRAFT"]);
const FINISHED = new Set(["ISSUED", "REJECTED", "CANCELLED"]);
const NEXT: Record<string, string> = {
  DRAFT: "Проверьте данные и отправьте заявку",
  NEED_INFO: "Добавьте документы по запросу банка",
  COUNTER_OFFER: "Сравните условия и размер переплаты",
  APPROVED: "Проверьте условия и перейдите к договору",
  SIGNING: "Ознакомьтесь с договором и подпишите",
  MANUAL_REVIEW: "Специалист изучает заявку. Ответ появится здесь",
  ISSUED: "Посмотрите договор и график платежей",
  REJECTED: "Посмотрите причины решения",
  CANCELLED: "Заявка отменена",
};
const FILTERS = [{id:"all",label:"Все заявки"}, {id:"action",label:"Ждут вас"}, {id:"active",label:"На рассмотрении"}, {id:"finished",label:"Завершённые"}] as const;
type Filter = typeof FILTERS[number]["id"];

export default function Dashboard() {
  const apps = useResource(api.applications, [], (d) => d?.some((a) => ACTIVE.has(a.status)) ? 3000 : null);
  const company = useResource(api.company, []);
  const fin = useResource(api.bankFinancials, []);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const items = apps.data ?? [];
  const needsAction = items.filter((a) => ACTION.has(a.status));
  const inReview = items.filter((a) => ACTIVE.has(a.status));
  const issued = items.filter((a) => a.status === "ISSUED");
  const visible = items.filter((a) =>
    (filter === "all" || (filter === "action" ? ACTION : filter === "active" ? ACTIVE : FINISHED).has(a.status)) &&
    (a.number + " " + a.product_name).toLocaleLowerCase("ru").includes(query.trim().toLocaleLowerCase("ru")),
  );
  const rank = (status: string) => status === "NEED_INFO" ? 0 : status === "DRAFT" ? 2 : 1;
  const priority = [...needsAction].sort((a, b) => rank(a.status) - rank(b.status))[0];

  return <div className="dashboard">
    <div className="dash-heading">
      <div><p className="eyebrow">Бизнес / Кредиты</p><h1>Финансирование бизнеса</h1></div>
      {company.data && <div className="company-caption"><b>{company.data.name}</b><span>ИНН {company.data.inn}</span></div>}
    </div>
    <section className="dash-focus" aria-label="Следующий шаг">
      <div className="focus-copy">
        <span className="eyebrow">{priority ? "Следующий шаг" : "От задачи — к решению"}</span>
        <h2>{priority ? NEXT[priority.status] : "Деньги для следующего шага вашего бизнеса"}</h2>
        <p>{priority ? priority.number + " · " + priority.product_name + ". Данные и документы сохраняются в заявке." : "Расскажите, на что нужны деньги. Подберём продукт, проверим данные и покажем условия и причины решения."}</p>
        <Link className="btn primary" to={priority ? "/applications/" + priority.id : "/new"}>{priority ? "Перейти к заявке" : "Подобрать финансирование"}<span aria-hidden="true">↗</span></Link>
      </div>
      <ol className="focus-route" aria-label="Как получить финансирование">
        <li><span>01</span><div><b>Задача бизнеса</b><small>Цель, сумма и срок</small></div></li>
        <li><span>02</span><div><b>Данные и проверка</b><small>Обороты, документы, история</small></div></li>
        <li><span>03</span><div><b>Понятное решение</b><small>Условия и следующий шаг</small></div></li>
      </ol>
    </section>
    <div className="dash-metrics" aria-label="Сводка заявок">
      <button onClick={() => setFilter("action")}><span>Ждут вашего действия</span><strong>{apps.data ? needsAction.length : "—"}</strong><small>Документы, условия или подпись <span aria-hidden="true">↗</span></small></button>
      <button onClick={() => setFilter("active")}><span>На рассмотрении</span><strong>{apps.data ? inReview.length : "—"}</strong><small>В конвейере или у специалиста <span aria-hidden="true">↗</span></small></button>
      <div><span>Кредитов выдано</span><strong>{apps.data ? issued.length : "—"}</strong><small>Симуляция выдачи в прототипе</small></div>
    </div>
    <div className="grid-main dash-body">
      <section className="panel applications-panel">
        <div className="panel-title"><h2>Ваши заявки</h2><Link to="/new" className="text-link">Новая заявка <span aria-hidden="true">+</span></Link></div>
        <div className="dash-filters" role="group" aria-label="Фильтр заявок">{FILTERS.map((f) => <button key={f.id} aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>{f.label}</button>)}</div>
        <label className="search-label"><span className="sr-only">Найти заявку по номеру или продукту</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg><input className="input" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Номер заявки или название продукта"/></label>
        <ErrorBox error={apps.error} onRetry={apps.reload}/>
        {apps.loading && !apps.data && <Loading/>}
        {apps.data && items.length === 0 && <div className="dash-empty"><span className="empty-number">01</span><h3>Начните с задачи бизнеса</h3><p>Заявка сохранится как черновик. Отправите её, когда всё проверите.</p><Link to="/new" className="btn primary">Создать первую заявку</Link></div>}
        {apps.data && items.length > 0 && visible.length === 0 && <div className="empty"><h3>Подходящих заявок нет</h3><p>Измените поиск или фильтр.</p><button className="btn text" onClick={() => {setFilter("all"); setQuery("");}}>Сбросить фильтры</button></div>}
        <div className="dash-app-list" aria-live="polite">{visible.map((a) => <Link key={a.id} to={"/applications/" + a.id} className="dash-app">
          <div className="dash-app-top"><span className="muted small">{a.number}</span><StatusChip code={a.status} title={a.status_title}/></div>
          <div className="dash-app-main"><h3>{a.product_name}</h3><b className="num">{money(a.amount)}</b></div>
          <p className="small muted">Запрос на {months(a.term_months)} · создана {date(a.created_at)}</p>
          <div className={"dash-app-next " + (ACTION.has(a.status) ? "action" : "")}><span>{NEXT[a.status] ?? "Проверяем данные. Результат появится в кабинете"}</span><span aria-hidden="true">→</span></div>
        </Link>)}</div>
        {!!apps.data && !!items.length && <p className="dash-list-count">Показано {visible.length} из {items.length}</p>}
      </section>
      <aside className="dash-aside">
        <section className="panel turnover-panel">
          <div className="panel-title"><h3>Обороты бизнеса</h3><span className="source-dot">Источник данных</span></div>
          {fin.data ? <><p className="small muted">Средние поступления в месяц</p><div className="amount-l num">{money(fin.data.avg_monthly_inflow)}</div><TurnoverBars fin={fin.data}/><p className="data-origin">Счёт в банке · {fin.data.months_count} мес.<br/>Данные подставятся в заявку автоматически</p></> : fin.loading ? <Loading/> : company.data?.is_bank_client && fin.error ? <ErrorBox error={fin.error} onRetry={fin.reload}/> : <><p>Выписка из вашего банка</p><p className="small muted" style={{marginTop:8}}>Загрузите CSV в заявку. Кабинет рассчитает поступления и покажет период данных.</p></>}
        </section>
        <section className="panel company-panel">
          <div className="panel-title"><h3>О компании</h3><span className="small muted">Реестр · симулятор</span></div>
          {company.data ? <dl className="kv-list"><dt>Статус</dt><dd>{company.data.registry_status === "ACTIVE" ? <span className="company-active">Действующая</span> : company.data.registry_status ? <span className="error-text">{company.data.registry_status}</span> : "Нет данных"}</dd><dt>Работает</dt><dd>{age(company.data.business_age_months)}</dd><dt>Деятельность</dt><dd>{company.data.okved_name ?? company.data.okved ?? "Нет данных"}</dd><dt>Руководитель</dt><dd>{company.data.director ?? "Нет данных"}</dd></dl> : company.error ? <ErrorBox error={company.error} onRetry={company.reload}/> : <Loading/>}
        </section>
        <p className="demo-caption">Учебный прототип для хакатона.<br/>Синтетические компании и данные. Решения не являются предложением банка.</p>
      </aside>
    </div>
  </div>;
}
