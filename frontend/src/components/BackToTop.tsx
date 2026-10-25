import { useEffect, useState } from "react";

export function BackToTop() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const update = () => {
      const editing = document.activeElement?.matches('input, textarea, select, [contenteditable="true"]');
      setVisible(window.scrollY > 400 && !editing);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
    return () => {
      window.removeEventListener("scroll", update);
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", update);
    };
  }, []);
  if (!visible) return null;
  return <button type="button" className="btn back-to-top" onClick={() => window.scrollTo({ top: 0, behavior: "auto" })} aria-label="Вернуться наверх">↑ Наверх</button>;
}
