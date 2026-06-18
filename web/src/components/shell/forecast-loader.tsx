import { WolfIcon } from "@/components/shell/wolf-icon";

interface ForecastLoaderProps {
  label?: string;
}

export function ForecastLoader({ label = "Howling..." }: ForecastLoaderProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-4 py-24 text-cream-faint"
      role="status"
      aria-live="polite"
    >
      <WolfIcon size={40} className="text-white" headClassName="howl motion-reduce:animate-none" />
      <span className="font-display text-[20px]">{label}</span>
    </div>
  );
}
