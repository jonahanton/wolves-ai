interface ChartHeadingProps {
  children: React.ReactNode;
}

export function ChartHeading({ children }: ChartHeadingProps) {
  return (
    <div className="mb-3">
      <p className="font-display text-[13.5px] leading-snug text-cream-dim">{children}</p>
    </div>
  );
}

interface AccentProps {
  colour: string;
  children: React.ReactNode;
}

export function Accent({ colour, children }: AccentProps) {
  return (
    <span className="font-semibold" style={{ color: colour }}>
      {children}
    </span>
  );
}
