import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorBox, Loading, TurnoverBars } from "../components/ui";
import { DocumentsBlock } from "../components/Documents";
import { api, type Application, type Product, type RecommendResult } from "../lib/api";
import { annuity, money, months, pct, uid } from "../lib/format";
import { useAction, useResource } from "../lib/hooks";

const STEPS = ["Задача", "Условия", "Данные о бизнесе", "Отправка"];

export default function NewApplication() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const purposes = useResource(api.purposes, []);
  const products = useResource(api.products, []);
  const fin = useResource(api.bankFinancials, []);

  const [purpose, setPurpose] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [rec, setRec] = useState<RecommendResult | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [amount, setAmount] = useState(1_000_000);
  const [term, setTerm] = useState(12);
  const [equipment, setEquipment] = useState({ equipment_name: "", equipment_cost: "", supplier: "" });
  const [draft, setDraft] = useState<Application | null>(null);
  const [consent, setConsent] = useState(false);
  const [idemKey] = useState(uid);
  const act = useAction();

  const pickPurpose = (code: string) =>
    act.run(async () => {
      setPurpose(code);
      const r = await api.recommend({ purpose: code });
      setRec(r);
      setProduct(null);
    });
  const describe = () =>
    act.run(async () => {
      const r = await api.recommend({ text });
      setRec(r);
      setPurpose(r.purpose);
      setProduct(null);
    });

  const choose = (p: Product) => {
    setProduct(p);
    setAmount((a) => Math.min(Math.max(a, p.min_amount), p.max_amount));
    setTerm((t) => Math.min(Math.max(t, p.min_term_months), p.max_term_months));
    setStep(1);
  };

  const payment = useMemo(() => {
    if (!product) return 0;
    return product.code === "OVERDRAFT" ? (amount * product.base_rate) / 100 / 12 : annuity(amount, product.base_rate, term);
  }, [product, amount, term]);
  const validTerms = !!product && Number.isFinite(amount) && amount >= product.min_amount && amount <= product.max_amount && Number.isInteger(term) && term >= product.min_term_months && term <= product.max_term_months;

  const saveDraft = () =>
    act.run(async () => {
      if (!product || !validTerms) return;
      const body = {
        product_code: product.code,
        purpose,
        purpose_comment: text || null,
        amount,
        term_months: term,
        collateral: product.requires_collateral
          ? {
              equipment_name: equipment.equipment_name || null,
              equipment_cost: equipment.equipment_cost ? Number(equipment.equipment_cost) : null,
              supplier: equipment.supplier || null,
            }
          : null,
      };
      const a = draft ? await api.update(draft.id, { ...body, version: draft.version }) : await api.create(body, idemKey);
      setDraft(a);
      setStep(2);
    });

  const submit = () =>
    act.run(async () => {
      if (!draft) return;
      const a = await api.submit(draft.id);
      nav(`/applications/${a.id}`, { replace: true });
    });

  if (purposes.loading || products.loading) return <Loading />;
  if (purposes.error || products.error) return <ErrorBox error={purposes.error || products.error} onRetry={() => { purposes.reload(); products.reload(); }} />;

  return (
    <div className="application-wizard">
      <Link to="/" className="back">← К заявкам</Link>
      <span className="eyebrow">НОВАЯ ЗАЯВКА</span>
      <h1>Получить финансирование</h1>
      <p className="muted" style={{ margin: "6px 0 20px" }}>Черновик сохраняется после второго шага — к нему можно вернуться из списка заявок.</p>
      <ol className="steps">
        {STEPS.map((s, i) => (
          <li key={s} className={i === step ? "on" : i < step ? "past" : ""} aria-current={i === step ? "step" : undefined}>
            <button className="step-button" disabled={i >= step} onClick={() => setStep(i)}><span className="n">{i < step ? "✓" : i + 1}</span>{s}</button>
          </li>
        ))}
      </ol>
      <div className="wizard-grid"><div className="wizard-content">
      {step === 0 && (
        <section className="panel stack gap-24">
          <div>
            <h2>На что нужны деньги?</h2>
            <p className="muted" style={{ marginTop: 4 }}>Не обязательно знать названия продуктов — выберите задачу, и мы подскажем подходящий вариант.</p>
          </div>
          <div className="purpose-grid">
            {purposes.data?.map((p) => (
              <button key={p.code} className="choice" disabled={act.busy} aria-pressed={purpose === p.code} onClick={() => pickPurpose(p.code)}>
                <span className="choice-title">{p.title}</span>
                <span className="choice-hint">{p.hint}</span>
              </button>
            ))}
          </div>
          <div className="field">
            <label htmlFor="describe">Или опишите своими словами</label>
            <div className="row">
              <input id="describe" className="input" placeholder="Например: покупатели платят через 60 дней, а аренду платить сейчас" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && text.trim() && describe()} />
              <button className="btn ghost" onClick={describe} disabled={!text.trim() || act.busy}>Подобрать</button>
            </div>
          </div>
          <ErrorBox error={act.error} />

          {rec && (
            <div className="stack gap-16">
              <div>
                <h3>{rec.purpose_title ? `Для задачи «${rec.purpose_title}» подойдёт` : "Все продукты"}</h3>
                {rec.note && <p className="hint" style={{ marginTop: 4 }}>{rec.note}</p>}
              </div>
              {rec.recommendations.map((r) => (
                <button key={r.product.code} className="choice" onClick={() => choose(r.product)} aria-pressed={product?.code === r.product.code}>
                  <div className="product-option">
                    <div>
                      {r.rank === 1 && rec.purpose && <div className="rank">Лучше всего подходит</div>}
                      <div className="choice-title" style={{ fontSize: 17 }}>{r.product.name}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div className="choice-title num">от {pct(r.estimated_rate_from)}</div>
                      <div className="muted small">годовых</div>
                    </div>
                    <div className="choice-hint" style={{ gridColumn: "1 / -1" }}>{r.why}</div>
                    <div className="small muted" style={{ gridColumn: "1 / -1" }}>
                      {money(r.product.min_amount)} – {money(r.product.max_amount)}, {r.product.min_term_months === r.product.max_term_months ? months(r.product.max_term_months) : `${r.product.min_term_months}–${r.product.max_term_months} мес.`}
                      {r.product.requires_collateral ? ", залог — покупаемое оборудование" : ", без залога"}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {step === 1 && product && (
        <section className="panel stack gap-24">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>{product.name}</h2>
            <button className="btn text" onClick={() => setStep(0)}>Сменить продукт</button>
          </div>
          <div className="field">
            <label htmlFor="amount">{product.code === "OVERDRAFT" ? "Лимит овердрафта" : "Сумма"}</label>
            <div className="row">
              <input id="amount" type="range" min={product.min_amount} max={product.max_amount} step={50_000} value={amount} onChange={(e) => setAmount(Number(e.target.value))} />
              <input className="input num" style={{ width: 170 }} type="number" min={product.min_amount} max={product.max_amount} step={10_000} value={amount} onChange={(e) => setAmount(Number(e.target.value))} aria-label="Сумма в рублях" />
            </div>
            <span className="hint">От {money(product.min_amount)} до {money(product.max_amount)}</span>
          </div>
          {product.min_term_months !== product.max_term_months ? (
            <div className="field">
              <label htmlFor="term">Срок: {months(term)}</label>
              <input id="term" type="range" min={product.min_term_months} max={product.max_term_months} value={term} onChange={(e) => setTerm(Number(e.target.value))} />
              <span className="hint">От {product.min_term_months} до {product.max_term_months} месяцев</span>
            </div>
          ) : (
            <p className="hint">Лимит устанавливается на {months(product.max_term_months)} и продлевается.</p>
          )}

          {product.requires_collateral && (
            <div className="stack gap-16">
              <h3>Что покупаете</h3>
              <div className="field">
                <label htmlFor="eq-name">Оборудование</label>
                <input id="eq-name" className="input" placeholder="Например: фрезерный станок с ЧПУ" value={equipment.equipment_name} onChange={(e) => setEquipment({ ...equipment, equipment_name: e.target.value })} />
              </div>
              <div className="row wrap gap-16">
                <div className="field grow">
                  <label htmlFor="eq-cost">Стоимость, ₽</label>
                  <input id="eq-cost" className="input num" type="number" min={0} value={equipment.equipment_cost} onChange={(e) => setEquipment({ ...equipment, equipment_cost: e.target.value })} />
                </div>
                <div className="field grow">
                  <label htmlFor="eq-sup">Поставщик</label>
                  <input id="eq-sup" className="input" value={equipment.supplier} onChange={(e) => setEquipment({ ...equipment, supplier: e.target.value })} />
                </div>
              </div>
              <p className="hint">Банк финансирует до 90% стоимости, остальное — первоначальный взнос.</p>
            </div>
          )}

          <div className="calc">
            <div>
              <div className="muted small">{product.code === "OVERDRAFT" ? "Проценты при полном использовании лимита" : "Ежемесячный платёж"}</div>
              <div className="amount-l num">≈ {money(Math.round(payment))}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="muted small">Ставка</div>
              <div className="choice-title">от {pct(product.base_rate)}</div>
            </div>
            <p className="hint" style={{ flexBasis: "100%" }}>Это предварительный расчёт. Точные условия банк предложит после проверки.</p>
          </div>
          <ErrorBox error={act.error} />
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={saveDraft} disabled={act.busy || !validTerms}>{act.busy ? "Сохраняем…" : "Сохранить и продолжить"}</button>
          </div>
        </section>
      )}

      {step === 2 && draft && (
        <section className="panel stack gap-24">
          <h2>Данные о бизнесе</h2>
          {fin.loading ? <Loading /> : fin.error ? <ErrorBox error={fin.error} onRetry={fin.reload} /> : fin.data ? (
            <>
              <div className="callout good">Компания обслуживается в банке — обороты по счёту уже в заявке. Вводить выручку не нужно.</div>
              <TurnoverBars fin={fin.data} />
              <p className="small muted">В среднем {money(fin.data.avg_monthly_inflow)} в месяц за {months(fin.data.months_count)}.</p>
            </>
          ) : (
            <div className="callout info">
              У компании нет счёта в банке. Загрузите выписку из вашего банка за последние 6 месяцев в формате CSV — кабинет сам посчитает обороты.
              Можно отправить заявку и без неё: банк попросит выписку на этапе проверки.
            </div>
          )}
          {!fin.loading && !fin.error && (!fin.data || draft.product.requires_collateral) && (
            <DocumentsBlock app={draft} onChange={setDraft} needStatement={!fin.data} />
          )}
          <ErrorBox error={act.error} />
          <div className="row" style={{ justifyContent: "space-between" }}>
            <button className="btn text" onClick={() => setStep(1)}>Назад</button>
            <button className="btn primary" disabled={fin.loading || !!fin.error} onClick={() => setStep(3)}>Продолжить</button>
          </div>
        </section>
      )}

      {step === 3 && draft && (
        <section className="panel stack gap-24">
          <h2>Проверьте и отправьте</h2>
          <dl className="kv">
            <div><dt>Продукт</dt><dd>{draft.product.name}</dd></div>
            <div><dt>Сумма</dt><dd className="num">{money(draft.amount)}</dd></div>
            <div><dt>Срок</dt><dd>{months(draft.term_months)}</dd></div>
            <div><dt>Платёж</dt><dd className="num">≈ {money(draft.estimated_monthly_payment)}</dd></div>
            <div><dt>Обороты</dt><dd>{draft.financials?.months_count ? `${months(draft.financials.months_count)}, в среднем ${money(draft.financials.avg_monthly_inflow)}` : "Попросим выписку на проверке"}</dd></div>
            <div><dt>Документы</dt><dd>{draft.documents.length ? draft.documents.map((d) => d.filename).join(", ") : "Нет"}</dd></div>
          </dl>
          <p className="small muted">После отправки прототип проверит компанию и кредитную историю через локальные симуляторы ЕГРЮЛ, ФНС и БКИ. Ход проверки и результат появятся на странице заявки.</p>
          <label className="check">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>Даю согласие на обработку данных компании и запрос кредитной истории в бюро кредитных историй</span>
          </label>
          <ErrorBox error={act.error} />
          <div className="row" style={{ justifyContent: "space-between" }}>
            <button className="btn text" onClick={() => setStep(2)}>Назад</button>
            <button className="btn primary" onClick={submit} disabled={!consent || act.busy}>{act.busy ? "Отправляем…" : "Отправить заявку"}</button>
          </div>
        </section>
      )}
      </div><aside className="wizard-summary sticky panel">
        <span className="eyebrow">ВАША ЗАЯВКА</span>
        <h2>{product?.name ?? "Начнём с задачи бизнеса"}</h2>
        {product ? <><div className="summary-amount num">{money(amount)}</div><dl className="kv"><div><dt>Срок</dt><dd>{months(term)}</dd></div><div><dt>Ставка от</dt><dd>{pct(product.base_rate)}</dd></div><div><dt>{product.code === "OVERDRAFT" ? "Проценты при полном лимите" : "Платёж в месяц ≈"}</dt><dd className="num">{validTerms ? money(payment) : "Уточните сумму"}</dd></div></dl><p className="hint">Предварительный расчёт без комиссий. Условия после проверки могут измениться.</p></> : <p className="muted small">Выберите цель — покажем продукты, сумму и срок. Здесь будет предварительный расчёт.</p>}
        <div className="summary-note"><b>{draft ? "Черновик сохранён" : "Можно продолжить позже"}</b><p>{draft ? `Заявка ${draft.number} доступна в вашем кабинете.` : "Черновик появится в кабинете после выбора и сохранения условий."}</p></div>
      </aside></div>
    </div>
  );
}
