import { CrystalBallIcon } from "@/components/shell/crystal-ball-icon";

interface ForecastLoaderProps {
  label?: string;
}

export function ForecastLoader({ label = "Consulting the forecast" }: ForecastLoaderProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-cream-faint" role="status" aria-live="polite">
      <CrystalBallIcon size={40} className="animate-[spin_2.8s_linear_infinite] text-gold motion-reduce:animate-none" />
      <span className="font-mono text-[12px] uppercase tracking-[0.18em]">{label}</span>
    </div>
  );
}
