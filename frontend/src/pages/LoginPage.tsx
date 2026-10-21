import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Brand, ErrorBox } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useAction, useResource } from "../lib/hooks";

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, run } = useAction();
  const demo = useResource(api.demoAccounts, []);

  const enter = async (e: string, p: string) => {
    const user = await run(() => login(e, p));
    if (user) nav(user.role === "ANALYST" ? "/analyst" : "/", { replace: true });
  };
  const submit = (ev: FormEvent) => { ev.preventDefault(); enter(email, password); };

  const clients = demo.data?.filter((d) => d.role === "CLIENT") ?? [];
  const analysts = demo.data?.filter((d) => d.role === "ANALYST") ?? [];

  return (
    <div className="login-wrap">
      <aside className="login-side">
        <div>
          <div className="brand login-brand"><Brand /></div>
          <span className="eyebrow">ФИНАНСИРОВАНИЕ БИЗНЕСА</span>
          <h1 className="display">Бизнесу — деньги.<br />Вам — ясность.</h1>
          <p>Сравните условия, добавьте документы и узнайте причину решения. Каждый следующий шаг — в одном кабинете.</p>
          <div className="login-proof"><span>01</span><div><b>Условия без догадок</b><p>Платёж и переплата рядом, чтобы выбрать осознанно.</p></div></div>
          <div className="login-proof"><span>02</span><div><b>Документы по делу</b><p>Видно, что нужно банку и что уже получено.</p></div></div>
        </div>
        <div className="login-route" aria-label="Этапы финансирования">
          <div className="lit">Задача</div>
          <div className="lit">Заявка</div>
          <div className="lit">Проверка</div>
          <div>Решение</div>
          <div>Деньги</div>
        </div>
      </aside>

      <section className="login-main">
        <span className="eyebrow">КРЕДИТНЫЙ МАРШРУТ</span>
        <h2 style={{ fontSize: 30 }}>Вход в кабинет</h2>
        <p className="muted small" style={{ marginTop: 8 }}>Демонстрация для хакатона. Выберите компанию или войдите по тестовой учётной записи.</p>
        <form onSubmit={submit} className="stack gap-16" style={{ marginTop: 20 }}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="password">Пароль</label>
            <input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <ErrorBox error={error} />
          <button className="btn primary" disabled={busy}>{busy ? "Входим…" : "Войти"}</button>
        </form>

        {!!demo.data?.length && (
          <div style={{ marginTop: 36 }}>
            <h3>Выберите демосценарий</h3>
            <p className="muted small">Каждая компания проводит заявку по своему сценарию. Пароль у всех: demo2026.</p>
            <div className="demo-list">
              {clients.map((d) => (
                <button key={d.email} className="demo" onClick={() => enter(d.email, d.password)} disabled={busy}>
                  <b>{d.company_name}</b>
                  <span>{d.scenario}</span>
                  <em>{d.email}</em>
                </button>
              ))}
              {analysts.map((d) => (
                <button key={d.email} className="demo" onClick={() => enter(d.email, d.password)} disabled={busy} style={{ borderColor: "var(--ink)" }}>
                  <b>{d.full_name}</b>
                  <span>{d.scenario}</span>
                  <em>{d.email}</em>
                </button>
              ))}
            </div>
          </div>
        )}
        <ErrorBox error={demo.error} onRetry={demo.reload} />
        <p className="login-disclaimer">Синтетические компании, проверки, подпись и выдача. Реальные банковские операции не проводятся.</p>
      </section>
    </div>
  );
}
