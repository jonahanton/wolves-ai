import type { Bar } from "@/lib/distribution";
import { SAMPLES_PER_CELL } from "@/lib/distribution";

export interface WdlHover {
  clientX: number;
  clientY: number;
  label: string;
  hue: string;
  range: string;
  share: string;
}

export function wdlBarHover(
  e: { clientX: number; clientY: number },
  bar: Bar,
  label: string,
  hue: string,
): WdlHover {
  const draws = Math.round(bar.y * (bar.x1 - bar.x0) * SAMPLES_PER_CELL);
  return {
    clientX: e.clientX,
    clientY: e.clientY,
    label,
    hue,
    range: `${(bar.x0 * 100).toFixed(0)}-${(bar.x1 * 100).toFixed(0)}% chance`,
    share: `${draws} of ${SAMPLES_PER_CELL} model draws`,
  };
}
