import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ErrorBox, Loading, TurnoverBars } from "../components/ui";
import { ApplicationSummary } from "../components/ApplicationSummary";
import { TextField } from "../components/TextField";
import { DocumentsBlock } from "../components/Documents";
import { api, type Application, type Product, type RecommendResult } from "../lib/api";
import { annuity, money, months, pct, uid } from "../lib/format";
import { useAction, useResource } from "../lib/hooks";

const STEPS = ["Задача", "Условия", "Данные о бизнесе", "Отправка"];

export default function NewApplication() {
  const [params] = useSearchParams();
  const edit = params.get("edit");
  const copy = params.get("copy");
  const sourceId = Number(edit ?? copy);
  if ((edit !== null || copy !== null) && (!Number.isSafeInteger(sourceId) || sourceId <= 0 || (edit !== null && copy !== null))) return <ErrorBox error="Некорректная ссылка на заявку." />;
  const mode = edit !== null ? "edit" : "copy";
  return <ApplicationForm key={`${mode}-${sourceId}`} sourceId={sourceId || null} mode={mode} />;
}

export function ApplicationForm({ sourceId = null, mode = "copy" }: { sourceId?: number | null; mode?: "edit" | "copy" }) {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const purposes = useResource(api.purposes, []);
  const products = useResource(api.products, []);
  const fin = useResource(api.bankFinancials, []);
  const source = useResource(() => sourceId ? api.application(sourceId) : Promise.resolve(null), [sourceId]);
  const [initialized, setInitialized] = useState(!sourceId);
  const [initializationError, setInitializationError] = useState<string | null>(null);

  const [purpose, setPurpose] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [rec, setRec] = useState<RecommendResult | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [amount, setAmount] = useState(1_000_000);
  const [amountInput, setAmountInput] = useState<string | null>(null);
  const [term, setTerm] = useState(12);
  const [equipment, setEquipment] = useState({ equipment_name: "", equipment_cost: "", supplier: "" });
  const [draft, setDraft] = useState<Application | null>(null);
  const [consent, setConsent] = useState(false);
  const [idemKey] = useState(uid);
  const act = useAction();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [step]);

  useEffect(() => {
    if (!sourceId || !source.data || products.loading || initialized) return;
    const original = source.data;
    if (mode === "edit" && original.status.code !== "DRAFT") {
      setInitializationError("Редактировать можно только черновик. Используйте «Создать на основе» для новой заявки.");
      return;
    }
    const selected = products.data?.find((p) => p.code === original.product.code) ?? original.product;
    const alternatives = (products.data ?? []).filter((p) => p.code !== selected.code && (!original.purpose || p.purposes.includes(original.purpose)));
    setPurpose(original.purpose);
    setText(original.purpose_comment ?? "");
    setRec({
      purpose: original.purpose,
      purpose_title: original.purpose_title,
      engine: "rules",
      note: null,
      recommendations: [selected, ...alternatives].map((p, index) => ({ product: p, why: index === 0 ? "Продукт исходной заявки" : p.short_description, rank: index === 0 ? 0 : index + 2, estimated_rate_from: p.base_rate })),
    });
    setProduct(selected);
    setAmount(original.amount);
    setTerm(original.term_months);
    setEquipment({ equipment_name: original.collateral?.equipment_name ?? "", equipment_cost: original.collateral?.equipment_cost == null ? "" : String(original.collateral.equipment_cost), supplier: original.collateral?.supplier ?? "" });
    setDraft(mode === "edit" ? original : null);
    setConsent(false);
    setStep(1);
    setInitialized(true);
  }, [sourceId, source.data, products.loading, products.data, initialized, mode]);

  const pickPurpose = (code: string) => {
    setConsent(false);
    setProduct(null);
    setRec(null);
    setText("");
    if (purpose === code) { setPurpose(null); return; }
    setPurpose(code);
    return act.run(async () => setRec(await api.recommend({ purpose: code })));
  };
  const describe = () => act.run(async () => {
    setProduct(null);
    setRec(null);
    setConsent(false);
    const r = await api.recommend({ text });
    setRec(r);
    setPurpose(r.purpose);
  });

  const choose = (p: Product) => {
    setConsent(false);
    if (product?.code === p.code) { setProduct(null); return; }
    setProduct(p);
    setAmountInput(null);
    setAmount((a) => Math.min(Math.max(a, p.min_amount), p.max_amount));
    setTerm((t) => Math.min(Math.max(t, p.min_term_months), p.max_term_months));
  };

  const taskReady = !!rec && !!product && (!!(purpose || text.trim()) || initialized && !!sourceId);
  const conditionsReady = taskReady && !!product && Number.isFinite(amount) && amount >= product.min_amount && amount <= product.max_amount
    && Number.isInteger(term) && term >= product.min_term_months && term <= product.max_term_months;
  const canVisit = (target: number) => target === 0 || (target === 1 ? taskReady : conditionsReady && (target === 2 || !!draft));

  const payment = useMemo(() => {
    if (!product) return 0;
    return product.code === "OVERDRAFT" ? (amount * product.base_rate) / 100 / 12 : annuity(amount, product.base_rate, term);
  }, [product, amount, term]);

  const saveDraft = (nextStep = 2) =>
    act.run(async () => {
      if (!product || !conditionsReady) return;
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
      setConsent(false);
      setStep(nextStep);
    });

  const navigateStep = (target: number) => {
    if (act.busy || !canVisit(target) || target === step) return;
    setConsent(false);
    if (target >= 2 && step <= 1) return saveDraft(target);
    setStep(target);
  };

  const submit = () =>
    act.run(async () => {
      if (!draft) return;
      const a = await api.submit(draft.id);
      nav(`/applications/${a.id}`, { replace: true });
    });

  if (source.error || initializationError) return <ErrorBox error={source.error ?? initializationError} />;
  if (purposes.error || products.error) return <ErrorBox error={purposes.error ?? products.error}
    onRetry={() => { void purposes.reload(); void products.reload(); }} />;
  if (purposes.loading || products.loading || !initialized) return <Loading />;

  return (
    <div className="financing-page">
      <h1>{sourceId && mode === "edit" ? "Редактировать заявку" : "Получить финансирование"}</h1>
      <p className="muted" style={{ margin: "6px 0 20px" }}>{sourceId ? mode === "edit" ? `Черновик ${source.data?.number ?? ""}. Изменения сохранятся после шага «Условия».` : `На основе заявки ${source.data?.number ?? ""}. Проверьте условия и приложите документы заново.` : "Черновик сохраняется после второго шага — к нему можно вернуться из списка заявок."}</p>
      <div className="financing-layout">
      <div className="financing-main">
      <ol className="steps">
        {STEPS.map((s, i) => (
          <li key={s} className={i === step ? "on" : i < step ? "past" : ""}>
            <button type="button" className="step-button" aria-current={i === step ? "step" : undefined} disabled={i === step || !canVisit(i) || act.busy} onClick={() => navigateStep(i)}>
              <span className="n" aria-hidden="true">{i + 1}</span><span>{s}</span>
            </button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <section className="panel stack gap-24">
          <div>
            <h2>На что нужны деньги?</h2>
            <p className="muted" style={{ marginTop: 4 }}>Не обязательно знать названия продуктов — выберите задачу, и мы подскажем подходящий вариант.</p>
          </div>
          <div className="purpose-grid">
            {purposes.data?.map((p) => (
              <button key={p.code} className="choice" aria-pressed={purpose === p.code} disabled={act.busy} onClick={() => pickPurpose(p.code)}>
                <span className="choice-title">{p.title}</span>
                <span className="choice-hint">{p.hint}</span>
              </button>
            ))}
          </div>
          <div className="describe-row">
            <TextField id="describe" label="Или опишите задачу своими словами" placeholder="Например: закрыть кассовый разрыв" disabled={act.busy} value={text} onChange={(e) => { setText(e.target.value); setRec(null); setProduct(null); setPurpose(null); setConsent(false); }} onKeyDown={(e) => e.key === "Enter" && text.trim() && !act.busy && describe()} />
            <button className="btn ghost" onClick={describe} disabled={!text.trim() || act.busy}>Подобрать</button>
          </div>
          <ErrorBox error={act.error} />

          {rec && (
            <div className="stack gap-16">
              <div>
                <h3>{rec.purpose_title ? `Для задачи «${rec.purpose_title}» подойдёт` : "Все продукты"}</h3>
                {rec.note && <p className="hint" style={{ marginTop: 4 }}>{rec.note}</p>}
              </div>
              {rec.recommendations.map((r) => (
                <button key={r.product.code} className="choice product-choice" disabled={act.busy} onClick={() => choose(r.product)} aria-pressed={product?.code === r.product.code}>
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
          <div className="form-actions">
            <button className="btn primary" disabled={!taskReady || act.busy} onClick={() => navigateStep(1)}>Продолжить</button>
          </div>
        </section>
      )}

      {step === 1 && product && (
        <section className="panel stack gap-24">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2>{product.name}</h2>
            <button className="btn text" onClick={() => navigateStep(0)}>Сменить продукт</button>
          </div>
          <div className="field">
            <TextField id="amount-value" label={product.code === "OVERDRAFT" ? "Лимит овердрафта" : "Сумма кредита"} suffix="₽" className="num" inputMode="decimal" value={amountInput ?? amount.toLocaleString("ru-RU")} onChange={(e) => {
              const value = e.target.value.replace(/\s/g, "");
              if (!/^\d{0,12}([,.]\d{0,2})?$/.test(value)) return;
              setAmountInput(e.target.value);
              setAmount(Number(value.replace(",", ".")) || 0);
            }} onBlur={() => { setAmount(Math.min(product.max_amount, Math.max(product.min_amount, amount))); setAmountInput(null); }} />
            <input id="amount" aria-label="Сумма кредита — ползунок" type="range" min={product.min_amount} max={product.max_amount} step={50_000} value={amount} style={{ "--range-progress": `${Math.min(100, Math.max(0, (amount - product.min_amount) / (product.max_amount - product.min_amount) * 100))}%` } as CSSProperties} onChange={(e) => { setAmount(Number(e.target.value)); setAmountInput(null); }} />
            <span className="hint">От {money(product.min_amount)} до {money(product.max_amount)}</span>
          </div>
          {product.min_term_months !== product.max_term_months ? (
            <div className="field">
              <label htmlFor="term">Срок: {months(term)}</label>
              <input id="term" style={{ "--range-progress": `${(term - product.min_term_months) / (product.max_term_months - product.min_term_months) * 100}%` } as CSSProperties} type="range" min={product.min_term_months} max={product.max_term_months} value={term} onChange={(e) => setTerm(Number(e.target.value))} />
              <span className="hint">От {product.min_term_months} до {product.max_term_months} месяцев</span>
            </div>
          ) : (
            <TextField id="fixed-term" label="Срок действия лимита" value={months(product.max_term_months)} readOnly />
          )}

          {product.requires_collateral && (
            <div className="stack gap-16">
              <h3>Что покупаете</h3>
              <TextField id="eq-name" label="Оборудование" placeholder="Например: фрезерный станок с ЧПУ" value={equipment.equipment_name} onChange={(e) => setEquipment({ ...equipment, equipment_name: e.target.value })} />
              <div className="equipment-fields">
                <TextField id="eq-cost" label="Стоимость" suffix="₽" className="num" type="number" min={0} value={equipment.equipment_cost} onChange={(e) => setEquipment({ ...equipment, equipment_cost: e.target.value })} />
                <TextField id="eq-sup" label="Поставщик" value={equipment.supplier} onChange={(e) => setEquipment({ ...equipment, supplier: e.target.value })} />
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
          <div className="form-actions">
            <button className="btn ghost small" disabled={act.busy} onClick={() => navigateStep(0)}>← Назад</button>
            <button className="btn primary" onClick={() => saveDraft()} disabled={act.busy || !conditionsReady}>{act.busy ? "Сохраняем…" : "Сохранить и продолжить"}</button>
          </div>
        </section>
      )}

      {step === 2 && draft && (
        <section className="panel stack gap-24">
          <h2>Данные о бизнесе</h2>
          {(draft.financials ?? fin.data) ? (
            <>
              <div className="callout good">{(draft.financials ?? fin.data)?.source === "STATEMENT_UPLOAD" ? "Обороты рассчитаны по загруженной выписке." : "Компания обслуживается в банке — обороты по счёту уже в заявке. Вводить выручку не нужно."}</div>
              <TurnoverBars fin={(draft.financials ?? fin.data)!} />
              <p className="small muted">В среднем <strong className="money-value">{money((draft.financials ?? fin.data)!.avg_monthly_inflow)}</strong> в месяц за {months((draft.financials ?? fin.data)!.months_count)}.</p>
            </>
          ) : (
            <div className="callout info">
              История оборотов сейчас недоступна. Загрузите CSV-выписку: минимум 3 последовательных месяца, лучше 6; последний месяц — не старше 2 месяцев. Кабинет сам посчитает обороты.
              Можно отправить заявку и без неё: банк попросит выписку на этапе проверки.
            </div>
          )}
          {(!fin.data || draft.product.requires_collateral) && (
            <DocumentsBlock app={draft} onChange={setDraft} needStatement={!fin.data} />
          )}
          <ErrorBox error={act.error} />
          <div className="form-actions">
            <button className="btn ghost small" disabled={act.busy} onClick={() => navigateStep(1)}>← Назад</button>
            <button className="btn primary" disabled={act.busy || !canVisit(3)} onClick={() => navigateStep(3)}>Продолжить</button>
          </div>
        </section>
      )}

      {step === 3 && draft && (
        <section className="panel stack gap-24">
          <h2>Проверьте и отправьте</h2>
          <dl className="kv">
            <div><dt>Продукт</dt><dd>{draft.product.name}</dd></div>
            <div><dt>Сумма</dt><dd className="money-value">{money(draft.amount)}</dd></div>
            <div><dt>Срок</dt><dd>{months(draft.term_months)}</dd></div>
            <div><dt>Платёж</dt><dd className="money-value">≈ {money(draft.estimated_monthly_payment)}</dd></div>
            <div><dt>Обороты</dt><dd>{draft.financials?.months_count ? `${months(draft.financials.months_count)}, в среднем ${money(draft.financials.avg_monthly_inflow)}` : "Попросим выписку на проверке"}</dd></div>
            <div><dt>Документы</dt><dd>{draft.documents.length ? draft.documents.map((d) => d.filename).join(", ") : "Нет"}</dd></div>
          </dl>
          <p className="small muted">После отправки банк проверит компанию в реестрах ЕГРЮЛ/ЕГРИП и сервисе ФНС «Прозрачный бизнес», запросит кредитную историю и рассчитает условия. Обычно это занимает меньше минуты, статус обновляется прямо на странице заявки.</p>
          <label className="check">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>Даю согласие на обработку данных компании и запрос кредитной истории в бюро кредитных историй</span>
          </label>
          <ErrorBox error={act.error} />
          <div className="form-actions">
            <button className="btn ghost small" disabled={act.busy} onClick={() => navigateStep(2)}>← Назад</button>
            <button className="btn primary" onClick={submit} disabled={!consent || act.busy}>{act.busy ? "Отправляем…" : "Отправить заявку"}</button>
          </div>
        </section>
      )}
      </div>
      <ApplicationSummary
        purpose={purposes.data?.find((p) => p.code === purpose)?.title ?? rec?.purpose_title ?? (rec ? text.trim() || null : null)}
        product={product} amount={amount} term={term} payment={payment}
        financials={draft?.financials ?? fin.data} documents={draft?.documents.length ?? 0}
        businessReached={!!draft} step={step} busy={act.busy}
        onEdit={navigateStep}
      />
      </div>
    </div>
  );
}
