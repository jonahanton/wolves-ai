"use client";

interface EstimateToggleProps {
  on: boolean;
  onToggle: () => void;
  colour: string;
  code?: string;
}

export function EstimateToggle({ on, onToggle, colour, code }: EstimateToggleProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={on}
      title="Estimated shift from results since the last full forecast"
      className="group block shrink-0 cursor-pointer whitespace-nowrap text-right leading-tight transition-[opacity,transform] duration-200 hover:-translate-y-px motion-reduce:transform-none"
      style={{ opacity: on ? 1 : 0.6 }}
    >
      <span
        className="block font-display text-[11px] font-bold leading-tight tracking-[0.01em] underline decoration-dotted decoration-1 underline-offset-[3px] transition-opacity group-hover:opacity-80"
        style={{ color: colour, textDecorationColor: on ? colour : "var(--color-cream-faint)" }}
      >
        {code ? `${code} Est. shift` : "Est. shift"}
      </span>
      <span className="block font-display text-[10px] font-medium leading-tight tracking-[0.01em] text-cream-faint">
        from latest results
      </span>
    </button>
  );
}
