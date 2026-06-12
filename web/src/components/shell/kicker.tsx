interface KickerProps {
  children: React.ReactNode;
  className?: string;
}

export function Kicker({ children, className }: KickerProps) {
  return <div className={`kicker mb-[18px] ${className ?? ""}`}>{children}</div>;
}
