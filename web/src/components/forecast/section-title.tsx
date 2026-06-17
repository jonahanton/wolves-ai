interface SectionTitleProps {
  children: string;
  hint?: string;
}

export function SectionTitle({ children, hint }: SectionTitleProps) {
  return (
    <div className="mb-[clamp(12px,2vh,18px)]">
      <h2 className="font-display text-[clamp(16px,1.9vw,19px)] font-bold tracking-[-0.01em] text-cream">
        {children}
      </h2>
      {hint && <p className="mt-1 font-display text-[13px] leading-snug text-cream-dim">{hint}</p>}
    </div>
  );
}
