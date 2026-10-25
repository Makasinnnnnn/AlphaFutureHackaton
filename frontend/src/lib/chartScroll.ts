export function scrollChartWithWheel(
  element: { scrollLeft: number; scrollWidth: number; clientWidth: number },
  event: { deltaX: number; deltaY: number; deltaMode: number; ctrlKey: boolean; preventDefault: () => void },
) {
  if (event.ctrlKey) return; // Preserve browser zoom and trackpad pinch.
  const limit = Math.max(0, element.scrollWidth - element.clientWidth);
  if (!limit) return;
  const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
  const multiplier = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientWidth : 1;
  const next = Math.max(0, Math.min(limit, element.scrollLeft + delta * multiplier));
  if (next === element.scrollLeft) return; // At either edge, continue scrolling the page.
  event.preventDefault();
  element.scrollLeft = next;
}
