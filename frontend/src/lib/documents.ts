import type { Application } from "./api";

export function hasPendingAnalystRequest(app: Pick<Application, "documents" | "missing_items">): boolean {
  return (app.missing_items ?? []).some((item) => item.code === "ANALYST_REQUEST" && (
    item.document_ids_before_request === undefined ||
    !app.documents.some((document) => !item.document_ids_before_request!.includes(document.id))
  ));
}
