import { type Bar, SAMPLES_PER_CELL } from "@/lib/distribution";

export interface HoverInfo {
  clientX: number;
  clientY: number;
  title: string;
  hue: string;
  range: string;
  share: string;
}

export function barHover(
  e: { clientX: number; clientY: number },
  b: Bar,
  title: string,
  hue: string,
): HoverInfo {
  const samples = Math.round(b.y * SAMPLES_PER_CELL);
  return {
    clientX: e.clientX,
    clientY: e.clientY,
    title,
    hue,
    range: `WC win probability ${(b.x0 * 100).toFixed(1)}-${(b.x1 * 100).toFixed(1)}%`,
    share: `${samples} of ${SAMPLES_PER_CELL} simulated draws (${(b.y * 100).toFixed(0)}%)`,
  };
}
