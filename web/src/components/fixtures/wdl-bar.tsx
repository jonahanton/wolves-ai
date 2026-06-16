import type { WdlBar } from "@/lib/fixtures";
import type { RowColours } from "@/lib/team-colours";

interface WdlBarProps {
  bar: WdlBar;
  colours: RowColours;
  showDraw: boolean;
}

const BLUR_GAIN = 60;
const MAX_BLUR = 6;

function blurPx(sigma: number): number {
  return Math.min(MAX_BLUR, sigma * BLUR_GAIN);
}

// A soft divider sits over each boundary; its blur encodes the boundary's spread
// across the draws, so a confident call reads crisp and an unsure one reads soft.
function Divider({ left, blur }: { left: number; blur: number }) {
  if (blur <= 0.2) return null;
  return (
    <span
      aria-hidden
      className="pointer-events-none absolute inset-y-0"
      style={{
        left: `${left}%`,
        width: `${Math.max(2, blur)}px`,
        transform: "translateX(-50%)",
        background: "var(--color-night)",
        filter: `blur(${blur}px)`,
        opacity: 0.55,
      }}
    />
  );
}

export function WdlBar({ bar, colours, showDraw }: WdlBarProps) {
  const homePct = bar.home * 100;
  const drawPct = (showDraw ? bar.draw : 0) * 100;
  return (
    <span className="relative block h-[10px] w-full overflow-hidden rounded-[2px] bg-cream/8">
      <span className="absolute inset-y-0 left-0" style={{ width: `${homePct}%`, backgroundColor: colours.home, opacity: 0.9 }} />
      {showDraw && (
        <span
          className="absolute inset-y-0"
          style={{ left: `${homePct}%`, width: `${drawPct}%`, backgroundColor: colours.draw, opacity: 0.9 }}
        />
      )}
      <span
        className="absolute inset-y-0 right-0"
        style={{ width: `${100 - homePct - drawPct}%`, backgroundColor: colours.away, opacity: 0.9 }}
      />
      <Divider left={homePct} blur={blurPx(bar.sigmaHomeDraw)} />
      {showDraw && <Divider left={homePct + drawPct} blur={blurPx(bar.sigmaDrawAway)} />}
    </span>
  );
}
