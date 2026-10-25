import { useRef } from "react";
import { api, type Application } from "../lib/api";
import { money, months } from "../lib/format";
import { useAction } from "../lib/hooks";
import { ErrorBox } from "./ui";

function Upload({ app, kind, title, hint, accept, onChange }: {
  app: Application; kind: string; title: string; hint: string; accept: string; onChange: (a: Application) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const act = useAction();
  const doc = [...app.documents].reverse().find((d) => d.kind === kind);

  const upload = (f: File | undefined) => f && act.run(async () => onChange(await api.upload(app.id, kind, f)));

  return (
    <div className="stack gap-8">
      <div className={`dropzone ${doc ? "done" : ""}`}>
        <div className="grow">
          <div style={{ fontWeight: 600 }}>{title}</div>
          <div className="small muted">
            {doc ? (
              kind === "STATEMENT" && app.financials?.source === "STATEMENT_UPLOAD"
                ? `${doc.filename}: распознано ${months(app.financials.months_count)}, в среднем ${money(app.financials.avg_monthly_inflow)} в месяц`
                : `Загружен ${doc.filename}`
            ) : hint}
          </div>
        </div>
        <input ref={input} type="file" accept={accept} className="sr-only" onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} aria-label={title} />
        <button className="btn ghost small" onClick={() => input.current?.click()} disabled={act.busy}>
          {act.busy ? "Загружаем…" : doc ? "Заменить файл" : "Выбрать файл"}
        </button>
      </div>
      {doc?.parsed?.warnings?.map((w) => <div key={w} className="callout warn small">{w}</div>)}
      <ErrorBox error={act.error} />
    </div>
  );
}

export function DocumentsBlock({ app, onChange, needStatement, only }: {
  app: Application; onChange: (a: Application) => void; needStatement: boolean; only?: Set<string>;
}) {
  const show = (code: string) => !only || only.has(code);
  return (
    <div className="stack gap-16">
      {needStatement && show("STATEMENT") && (
        <Upload app={app} kind="STATEMENT" accept=".csv,text/csv" onChange={onChange}
          title="Выписка по расчётному счёту"
          hint="CSV: минимум 3 последовательных месяца, лучше 6. Последний месяц — не старше 2 месяцев. Колонки «Дата» и «Сумма» или «Приход»/«Расход»." />
      )}
      {app.product.requires_collateral && show("EQUIPMENT_INVOICE") && (
        <Upload app={app} kind="EQUIPMENT_INVOICE" accept=".pdf,.png,.jpg,.jpeg" onChange={onChange}
          title="Счёт или спецификация на оборудование"
          hint="PDF или фото документа от поставщика" />
      )}
      {only?.has("OTHER") && (
        <Upload app={app} kind="OTHER" accept=".pdf,.png,.jpg,.jpeg,.csv" onChange={onChange}
          title="Документ по запросу специалиста" hint="PDF, CSV или фото" />
      )}
    </div>
  );
}
