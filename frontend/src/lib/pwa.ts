export function registerPwa() {
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
  const register = () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).catch(() => {
      // Installation is optional; a failure must not interrupt the online credit flow.
    });
  };
  if (document.readyState === 'complete') register();
  else window.addEventListener('load', register, { once: true });
}
