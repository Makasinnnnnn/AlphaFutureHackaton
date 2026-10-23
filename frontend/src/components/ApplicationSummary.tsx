import { useState } from "react";
import { type Financials, type Product } from "../lib/api";
import { money, months, pct } from "../lib/format";

interface Props {
  purpose: string | null;
  product: Product | null;
  amount: number;
  term: number;
  payment: number;
  financials: Financials | null | undefined;
  documents: number;
  businessReached: boolean;
  step: number;
  busy: boolean;
  onEdit: (step: number) => void;
}

export function ApplicationSummary({ purpose, product, amount, term, payment, financials, documents, businessReached, step, busy, onEdit }: Props) {
  const [open, setOpen] = useState(false);
  const edit = (target: number, name: string) => target < step && <button className="summary-edit" type="button" disabled={busy} onClick={() => onEdit(target)} aria-label={`Изменить ${name}`}>Изменить</button>;
  return <aside className={`application-summary${open ? " is-open" : ""}`} aria-label="Сводка текущей заявки">
    <div className="summary-heading"><h2>Ваша заявка</h2><button type="button" className="summary-toggle" aria-expanded={open} aria-controls="application-summary-details" onClick={() => setOpen(!open)}>{open ? "Свернуть −" : "Подробнее +"}</button></div>
    <p className="summary-caption">{product ? `${money(amount)} · ${months(term)}` : "Собираем условия по шагам"}</p>
    <div className="summary-details" id="application-summary-details">
      {!purpose && <p className="hint">Выберите задачу — здесь появятся цель, продукт и условия финансирования.</p>}
      {purpose && <section className="summary-section"><div className="summary-label">Задача{edit(0, "задачу")}</div><p>{purpose}</p></section>}
      {product && <>
        <section className="summary-section"><div className="summary-label">Продукт{edit(0, "продукт")}</div><p>{product.name}</p><span className="summary-rate">от {pct(product.base_rate)} годовых</span></section>
        <section className="summary-section"><div className="summary-label">Условия{edit(1, "условия")}</div><dl className="summary-values">
          <div><dt>{product.code === "OVERDRAFT" ? "Лимит" : "Сумма"}</dt><dd>{money(amount)}</dd></div>
          <div><dt>Срок</dt><dd>{months(term)}</dd></div>
          <div className="summary-payment"><dt>{product.code === "OVERDRAFT" ? "Проценты в месяц при полном лимите" : "Платёж в месяц"}</dt><dd>≈ {money(Math.round(payment))}</dd></div>
        </dl></section>
      </>}
      {businessReached && <section className="summary-section"><div className="summary-label">Данные о бизнесе{edit(2, "данные о бизнесе")}</div>
        {financials?.months_count ? <><p className="num">{money(financials.avg_monthly_inflow)} <span className="hint">в месяц</span></p><p className="hint">Средние поступления за {months(financials.months_count)}</p><p className="hint">{financials.source_label}</p></> : <p className="hint">Обороты пока не подтверждены выпиской</p>}
        <p className="summary-documents">Документов приложено: {documents}</p>
      </section>}
      {product && <p className="summary-disclaimer">Ставка и платёж предварительные. Точные условия банк предложит после проверки заявки.</p>}
    </div>
  </aside>;
}
