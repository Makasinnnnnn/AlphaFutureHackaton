import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Notification } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime } from "../lib/format";
import { useResource } from "../lib/hooks";

const changed = () => window.dispatchEvent(new Event("notifications-changed"));
export function useNotifications() {
  const { user } = useAuth();
  const resource = useResource(api.notifications, [user?.id], () => 5000);
  useEffect(() => {
    const refresh = () => { void resource.reload(); };
    window.addEventListener("notifications-changed", refresh);
    return () => window.removeEventListener("notifications-changed", refresh);
  }, [resource.reload]);
  return resource;
}

export function NotificationList({ items, onOpen }: { items: Notification[]; onOpen?: () => void }) {
  const { user } = useAuth();
  const base = user?.role === "ANALYST" ? "/analyst/applications" : "/applications";
  const [menu, setMenu] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMenu(null); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  const remove = async (id: number) => {
    setBusy(id); setError(null);
    try { await api.deleteNotification(id); setMenu(null); changed(); }
    catch { setError("Не удалось удалить уведомление. Попробуйте ещё раз."); }
    finally { setBusy(null); }
  };
  const open = (notification: Notification) => {
    setMenu(null);
    if (!notification.is_read) void api.readNotification(notification.id).then(changed).catch(() => {});
    onOpen?.();
  };
  return <div className="notification-list">
    {error && <p className="error-text" role="alert">{error}</p>}
    {!items.length && <div className="notification-empty">Уведомлений пока нет</div>}
    {items.map((n) => <article key={n.id} className={`notification-item ${n.is_read ? "" : "is-unread"}`}>
      {n.application_id ? <Link className="notification-link" to={`${base}/${n.application_id}`} onClick={() => open(n)}>
        <span className="notification-indicator" aria-label={n.is_read ? "Прочитано" : "Новое"} />
        <span className="notification-content"><strong>{n.title}</strong><span>{n.body}</span><time dateTime={n.created_at}>{dateTime(n.created_at)}</time></span>
        <span className="notification-arrow" aria-hidden="true">↗</span>
      </Link> : <div className="notification-link"><span className="notification-indicator" /><span className="notification-content"><strong>{n.title}</strong><span>{n.body}</span><time dateTime={n.created_at}>{dateTime(n.created_at)}</time></span></div>}
      <button className="notification-more" type="button" aria-label={`Действия с уведомлением «${n.title}»`} aria-expanded={menu === n.id} aria-haspopup="menu" onClick={() => setMenu(menu === n.id ? null : n.id)}>⋯</button>
      {menu === n.id && <div className="notification-menu" role="menu"><button type="button" role="menuitem" disabled={busy === n.id} onClick={() => remove(n.id)}>{busy === n.id ? "Удаляем…" : "Удалить уведомление"}</button></div>}
    </article>)}
  </div>;
}
