import { WOLF_VARIANTS, type WolfMood, type WolfVariant } from "@/components/mascot/variants";
import { cn } from "@/lib/utils";

export type { WolfMood, WolfVariant } from "@/components/mascot/variants";

interface WolfMascotProps {
  mood?: WolfMood;
  variant?: WolfVariant;
  size?: number;
  className?: string;
}

function Eyes({ mood }: { mood: WolfMood }) {
  if (mood === "happy") {
    return (
      <g className="wolf-eyes" stroke="#23262b" strokeWidth="2.4" strokeLinecap="round" fill="none">
        <path d="M37 37 q4 -4.5 8 0" />
        <path d="M51 37 q4 -4.5 8 0" />
      </g>
    );
  }
  return (
    <g className="wolf-eyes" fill="#23262b">
      <circle cx="41" cy="36.5" r="2.7" />
      <circle cx="55" cy="36.5" r="2.7" />
      {mood === "worried" && (
        <g stroke="#23262b" strokeWidth="2" strokeLinecap="round">
          <path d="M36.5 30.5 l8 2.4" />
          <path d="M59.5 30.5 l-8 2.4" />
        </g>
      )}
    </g>
  );
}

function Mouth({ mood }: { mood: WolfMood }) {
  if (mood === "happy") {
    return <path d="M43 53.5 q5 4 10 0" stroke="#23262b" strokeWidth="2" strokeLinecap="round" fill="none" />;
  }
  if (mood === "worried") {
    return <path d="M44 54.5 q4 -2.4 8 0" stroke="#23262b" strokeWidth="2" strokeLinecap="round" fill="none" />;
  }
  return <path d="M44 54 h8" stroke="#23262b" strokeWidth="2" strokeLinecap="round" fill="none" />;
}

export function WolfMascot({ mood = "neutral", variant = "idle", size = 56, className }: WolfMascotProps) {
  const config = WOLF_VARIANTS[variant];
  return (
    <svg
      viewBox="0 0 96 96"
      width={size}
      height={size}
      role="img"
      aria-label={`Wolf mascot, ${mood}`}
      style={{ overflow: "visible" }}
      className={cn("wolf shrink-0", config.className, className)}
    >
      <g className="wolf-all">
        <g className="wolf-tail">
          <path d="M70 88 q11 0 13 -10 q1 -6 -3 -9 q-1 4 -3 8 q-3 7 -10 8 Z" fill="#7e858f" />
        </g>
        <g className="wolf-body">
          <g fill="#f6f6f3" stroke="#c6c6c0" strokeWidth="1.5">
            <path d="M23 96 V79 q0 -11 11 -14 l10 -3 h8 l10 3 q11 3 11 14 v17 Z" />
          </g>
          <path d="M38 62 l10 7 10 -7 -10 -2 Z" fill="#1e2a52" />
          <g fill="#ce1124">
            <rect x="30" y="74" width="11" height="11" rx="1.5" fill="none" stroke="#ce1124" strokeWidth="1.4" />
            <rect x="34.5" y="75" width="2" height="9" />
            <rect x="31" y="78.5" width="9" height="2" />
          </g>
        </g>
        <g className="wolf-head">
          <g className="wolf-ear wolf-ear-l">
            <path d="M29 6 L22 31 L42 21 Z" fill="#7e858f" />
            <path d="M30 12 L26 27 L38 21 Z" fill="#565b63" />
          </g>
          <g className="wolf-ear wolf-ear-r">
            <path d="M67 6 L74 31 L54 21 Z" fill="#7e858f" />
            <path d="M66 12 L70 27 L58 21 Z" fill="#565b63" />
          </g>
          <path
            d="M48 15 C33 15 25 25 25 38 c0 9 5 15 13 19 l5 5 h10 l5 -5 c8 -4 13 -10 13 -19 0 -13 -8 -23 -23 -23 Z"
            fill="#8d939e"
          />
          <path d="M48 41 c-7 0 -12 4 -12 9 0 5 5 9 12 9 7 0 12 -4 12 -9 0 -5 -5 -9 -12 -9 Z" fill="#ece9e2" />
          <path d="M44 44 h8 l-4 5.5 Z" fill="#2b2e33" />
          <Eyes mood={mood} />
          <Mouth mood={mood} />
        </g>
      </g>
      {config.showHowlMarks && (
        <g
          className="wolf-howl-marks"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path className="wolf-howl-1" d="M72 22 q4 -4 3 -9" />
          <path className="wolf-howl-2" d="M78 27 q6 -6 5 -14" />
        </g>
      )}
      {config.showBall && (
        <g className="wolf-ball">
          <circle cx="80" cy="88" r="7" fill="#f6f6f3" stroke="#23262b" strokeWidth="1.4" />
          <path d="M80 84.5 l3.3 2.4 -1.3 3.9 h-4 l-1.3 -3.9 Z" fill="#23262b" />
        </g>
      )}
    </svg>
  );
}
