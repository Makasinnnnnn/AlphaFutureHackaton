import { useEffect, useState } from "react";

export function BackToTop() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const update = () => setVisible(window.scrollY > 400);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);
  if (!visible) return null;
  return <button type="button" className="btn back-to-top" onClick={() => window.scrollTo({ top: 0, behavior: "auto" })} aria-label="Вернуться наверх">↑ Наверх</button>;
}
