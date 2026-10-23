import { useState } from "react";
import { NotificationList, useNotifications } from "../components/Notifications";
import { ErrorBox, Loading } from "../components/ui";
import { api } from "../lib/api";

export default function NotificationsPage() {
  const resource = useNotifications();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const readAll = async () => {
    setBusy(true); setError(null);
    try { await api.readAll(); window.dispatchEvent(new Event("notifications-changed")); }
    catch { setError("Не удалось отметить уведомления прочитанными."); }
    finally { setBusy(false); }
  };
  return <>
    <div className="page-head"><h1>Уведомления</h1><button className="btn ghost" disabled={busy || !resource.data?.unread} onClick={readAll}>Прочитать все</button></div>
    <section className="panel notifications-page">
      <ErrorBox error={resource.error ?? error} onRetry={resource.reload} />
      {resource.loading && !resource.data ? <Loading /> : <NotificationList items={resource.data?.items ?? []} />}
    </section>
  </>;
}
