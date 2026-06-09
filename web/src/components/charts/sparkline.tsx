import { sparklineGeometry } from "@/lib/sparkline";

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
}

export function Sparkline({ values, width = 64, height = 20, className }: SparklineProps) {
  const geometry = sparklineGeometry(values, width, height);
  if (!geometry) return null;

  return (
    <svg width={width} height={height} className={className} aria-hidden>
      <line
        x1="0"
        y1={geometry.endPoint.y}
        x2={width}
        y2={geometry.endPoint.y}
        stroke="var(--border)"
        strokeWidth="1"
      />
      {geometry.path && (
        <path d={geometry.path} fill="none" stroke="var(--gold)" strokeWidth="1.5" strokeLinecap="round" />
      )}
      <circle cx={geometry.endPoint.x} cy={geometry.endPoint.y} r="2.2" fill="var(--gold)" />
    </svg>
  );
}
