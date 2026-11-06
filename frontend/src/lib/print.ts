/** Save as PDF without a PDF library: wake every lazy chart, give them a moment to draw, then print.
 * data-print on <html> switches the CSS tokens to the light print set, so canvases redraw readable on paper. */
import { dur } from "./motion.ts";

export const PREPARE_PRINT = "tp:prepare-print";

export function setPrintMode(on: boolean) {
  if (on) document.documentElement.dataset.print = "1";
  else delete document.documentElement.dataset.print;
}

export function printPage() {
  window.dispatchEvent(new Event(PREPARE_PRINT));
  // Charts below the fold load ECharts and draw now; wait for that before the dialog freezes the page.
  window.setTimeout(() => window.print(), dur.standard() * 1000 + 900);
}
