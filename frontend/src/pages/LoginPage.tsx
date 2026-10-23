import { TextField } from "../components/TextField";
import { BrandMark } from "../components/BrandMark";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorBox } from "../components/ui";
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
          <div className="row gap-8" style={{ marginBottom: 48 }}>
            <BrandMark />
            <b>Кредитный кабинет для бизнеса</b>
          </div>
          <h1 className="display">Кредит без походов в банк и без догадок</h1>
          <p>Выберите, на что нужны деньги, — кабинет подскажет продукт, сам подтянет обороты и реквизиты и покажет, на каком этапе заявка прямо сейчас.</p>
        </div>
        <div className="login-route" aria-hidden>
          <div className="lit">Задача</div>
          <div className="lit">Заявка</div>
          <div className="lit">Проверка</div>
          <div>Решение</div>
          <div>Деньги</div>
        </div>
      </aside>

      <section className="login-main">
        <h2 style={{ fontSize: 24 }}>Вход</h2>
        <form onSubmit={submit} className="stack gap-16" style={{ marginTop: 20 }}>
          <TextField id="email" label="Email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <TextField id="password" label="Пароль" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <ErrorBox error={error} />
          <button className="btn primary" disabled={busy}>{busy ? "Входим…" : "Войти"}</button>
        </form>

        {!!demo.data?.length && (
          <div style={{ marginTop: 36 }}>
            <h3>Тестовые учётные записи</h3>
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
      </section>
    </div>
  );
}
