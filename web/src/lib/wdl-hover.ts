import type { Bar } from "@/lib/distribution";

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
  samples: number,
): WdlHover {
  const draws = Math.round(bar.y * (bar.x1 - bar.x0) * samples);
  return {
    clientX: e.clientX,
    clientY: e.clientY,
    label,
    hue,
    range: `${(bar.x0 * 100).toFixed(0)}-${(bar.x1 * 100).toFixed(0)}% chance`,
    share: `${draws} of ${samples} model draws`,
  };
}
